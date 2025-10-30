from datetime import date, datetime
from typing import List, Tuple, Union, Optional

from dateutil.relativedelta import relativedelta
import numpy as np

from ficclib.bond.utils.date import to_date
from ficclib.bond.ktb.curve_types import DiscountFactorNode

DAYS_IN_YEAR = 365


class KTB:
    def __init__(
        self,
        issue: Union[date, datetime, str],
        maturity: Union[date, datetime, str],
        coupon: float,
        pymt_freq: int = 6,
        face_value: float = 10000,
    ):
        """Korean Treasury Bond.

        Args:
            issue: Issue date
            maturity: Maturity date
            coupon: Annual coupon rate in percent (e.g., 3.5)
            pymt_freq: Months between coupons (default: 6)
            face_value: Par value (default: 10000)
        """
        self.issue = to_date(issue)
        self.maturity = to_date(maturity)
        self.coupon = float(coupon)
        self.pymt_freq = int(pymt_freq)
        self.face_value = float(face_value)

        if self.maturity <= self.issue:
            raise ValueError("Maturity must be after issue date")
        if coupon < 0:
            raise ValueError("Coupon rate must be non-negative")
        if pymt_freq <= 0:
            raise ValueError("Coupon term must be positive")

        self._term_to_next_coupon: Optional[float] = None

    # Properties
    @property
    def coupon_rate(self) -> float:
        """Coupon rate in decimal form."""
        return self.coupon / 100

    @property
    def coupons_per_year(self) -> float:
        """Number of coupon payments per year."""
        return 12 / self.pymt_freq

    # Cash flow methods
    def coupon_amount(self) -> float:
        """Per-period coupon amount."""
        return self.face_value * self.coupon_rate / self.coupons_per_year

    def payment_schedule(self) -> List[date]:
        """List of coupon payment dates."""
        dates = []
        current_date = self.issue + relativedelta(months=self.pymt_freq)

        while current_date <= self.maturity:
            dates.append(current_date)
            current_date += relativedelta(months=self.pymt_freq)

        return dates or [self.maturity]

    def cash_flows(self) -> List[Tuple[date, float]]:
        """Cash flows as (date, amount) tuples. Final payment includes principal."""
        dates = self.payment_schedule()
        coupon = self.coupon_amount()

        if not dates:
            return []

        flows = [(dt, coupon) for dt in dates[:-1]]
        flows.append((dates[-1], self.face_value + coupon))
        return flows

    def adjacent_payment_dates(
        self, as_of: Union[date, datetime, str]
    ) -> Tuple[date, date]:
        """Return (previous, next) payment dates around as_of date."""
        as_of_dt = to_date(as_of)
        dates = self.payment_schedule()

        if not dates or as_of_dt < dates[0]:
            return self.issue, dates[0] if dates else self.maturity

        for i, dt in enumerate(dates):
            if dt > as_of_dt:
                return dates[i - 1] if i > 0 else self.issue, dt

        return dates[-1], dates[-1]

    # Pricing methods
    def price(
        self, ytm_percent: float, valuation_date: Union[date, datetime, str]
    ) -> float:
        """Calculate bond price using yield-to-maturity."""
        return self.dirty_price(ytm_percent, valuation_date)

    def dirty_price(
        self, ytm_percent: float, valuation_date: Union[date, datetime, str]
    ) -> float:
        """Calculate dirty price using yield-to-maturity."""
        ytm = ytm_percent / 100
        val_date = to_date(valuation_date)
        flows = self.cash_flows()

        if not flows or val_date >= flows[-1][0]:
            return 0.0

        prev_pmt, next_pmt = self.adjacent_payment_dates(val_date)
        remaining_payments = sum(1 for dt, _ in flows if dt >= next_pmt)

        # Price at next coupon date
        discount_rate = 1 + ytm / 2
        coupon = self.coupon_amount()

        price_at_next = sum(
            coupon / discount_rate**i for i in range(remaining_payments)
        )
        price_at_next += self.face_value / discount_rate ** (remaining_payments - 1)

        # Adjust back to valuation date
        days_to_next = (next_pmt - val_date).days
        days_in_period = max((next_pmt - prev_pmt).days, 1)
        accrual_factor = days_to_next / days_in_period

        return price_at_next / (1 + accrual_factor * ytm / 2)

    def price_from_zero_curve(
        self, valuation_date: date, dfs: List[DiscountFactorNode]
    ) -> float:
        """Calculate bond price using zero-coupon discount factors."""
        val_date = to_date(valuation_date)
        flows = self.cash_flows()
        price = 0.0

        for coupon_date, amount in flows:
            if coupon_date > val_date:
                time_to_coupon = (coupon_date - val_date).days / DAYS_IN_YEAR
                df = self._log_linear_interpolation(
                    [node.years_from_valuation for node in dfs],
                    [node.discount_factor for node in dfs],
                    time_to_coupon,
                )
                price += amount * df

        return price

    def forward(self, valuation_date: date, forward_mat_date: date, dfs) -> float:
        """Calculate forward price of the bond."""
        val_date = to_date(valuation_date)
        fwd_date = to_date(forward_mat_date)

        # Get spot price
        maturity_time = (self.maturity - val_date).days / DAYS_IN_YEAR
        maturity_df = self._log_linear_interpolation(dfs[0], dfs[1], maturity_time)
        spot_price = self.zeros(dfs, val_date, maturity_df)

        # Calculate intermediate coupons
        num_coupons = round(
            self._months_between(self.issue, self.maturity) / self.pymt_freq
        )
        intermediate_coupons = 0.0

        for i in range(1, num_coupons + 1):
            coupon_date = self.issue + relativedelta(months=self.pymt_freq * i)
            if val_date < coupon_date <= fwd_date:
                time_to_coupon = (coupon_date - val_date).days / DAYS_IN_YEAR
                df = self._log_linear_interpolation(dfs[0], dfs[1], time_to_coupon)
                intermediate_coupons += (
                    self.face_value * self.coupon_rate / self.coupons_per_year
                ) * df

                if i == num_coupons:  # Add principal
                    intermediate_coupons += self.face_value * df

        # Calculate forward price
        forward_time = (fwd_date - val_date).days / DAYS_IN_YEAR
        forward_df = self._log_linear_interpolation(dfs[0], dfs[1], forward_time)

        return (spot_price - intermediate_coupons) / forward_df

    # Risk metrics
    def modified_duration(
        self, ytm: float, valuation_date: date, dirty_price: Optional[float] = None
    ) -> float:
        """Calculate modified duration. YTM expected as percent."""
        ytm_decimal = ytm / 100
        val_date = to_date(valuation_date)

        if dirty_price is None:
            dirty_price = self.dirty_price(ytm, val_date)

        term_to_next = self._get_term_to_next_coupon(val_date)
        num_coupons = round(
            self._months_between(self.issue, self.maturity) / self.pymt_freq
        )
        duration = 0.0
        power = 0

        for i in range(1, num_coupons + 1):
            coupon_date = self.issue + relativedelta(months=self.pymt_freq * i)
            if coupon_date > val_date:
                discount_factor = (1 + ytm_decimal / self.coupons_per_year) ** power
                present_value = (
                    self.face_value * self.coupon_rate / self.coupons_per_year
                ) / discount_factor

                if i == num_coupons:
                    present_value += self.face_value / discount_factor

                present_value /= (
                    1 + (ytm_decimal / self.coupons_per_year) * term_to_next
                )
                weight = present_value / dirty_price
                duration += weight * (coupon_date - val_date).days / DAYS_IN_YEAR
                power += 1

        return duration / (1 + ytm_decimal / self.coupons_per_year)

    def convexity(
        self, ytm: float, valuation_date: date, dirty_price: Optional[float] = None
    ) -> float:
        """Calculate convexity. YTM expected as percent."""
        ytm_decimal = ytm / 100
        val_date = to_date(valuation_date)

        if dirty_price is None:
            dirty_price = self.dirty_price(ytm, val_date)

        term_to_next = self._get_term_to_next_coupon(val_date)
        num_coupons = round(
            self._months_between(self.issue, self.maturity) / self.pymt_freq
        )
        convexity = 0.0
        power = 0

        for i in range(1, num_coupons + 1):
            coupon_date = self.issue + relativedelta(months=self.pymt_freq * i)
            if coupon_date > val_date:
                discount_factor = (1 + ytm_decimal / self.coupons_per_year) ** power
                present_value = (
                    self.face_value * self.coupon_rate / self.coupons_per_year
                ) / discount_factor

                if i == num_coupons:
                    present_value += self.face_value / discount_factor

                present_value /= (
                    1 + (ytm_decimal / self.coupons_per_year) * term_to_next
                )
                weight = present_value / dirty_price
                time_to_payment = (coupon_date - val_date).days / DAYS_IN_YEAR

                convexity += (
                    weight
                    * time_to_payment
                    * (time_to_payment + 1 / self.coupons_per_year)
                )
                power += 1

        return convexity / ((1 + ytm_decimal / self.coupons_per_year) ** 2)

    # Helper methods
    def _months_between(self, start: date, end: date) -> int:
        """Calculate months between two dates."""
        return (end.year - start.year) * 12 + end.month - start.month

    def _get_term_to_next_coupon(self, valuation_date: date) -> float:
        """Calculate fraction of coupon period remaining."""
        if self._term_to_next_coupon is None:
            prev_pmt, next_pmt = self.adjacent_payment_dates(valuation_date)
            if prev_pmt != next_pmt:
                self._term_to_next_coupon = (next_pmt - valuation_date).days / (
                    next_pmt - prev_pmt
                ).days
            else:
                self._term_to_next_coupon = 0.0
        return self._term_to_next_coupon

    @staticmethod
    def _log_linear_interpolation(x_values, y_values, x_target):
        """Log-linear interpolation."""
        return float(np.exp(np.interp(x_target, x_values, np.log(y_values))))