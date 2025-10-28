from datetime import datetime
from typing import List, Tuple

from sympy import Symbol, nsolve

from .bond import KTB
from .params_loader import FuturesParams
from ficclib.utils.date import to_date, futures_termination_date


class KTB_Futures:
    def __init__(self, params: FuturesParams):
        self.params = params

    def _adjacent_payment_dates(
        self,
        as_of_dt: datetime,
        flows: List[Tuple[datetime, float]],
        issue_dt: datetime,
    ) -> Tuple[datetime, datetime]:
        if as_of_dt < flows[0][0]:
            return issue_dt, flows[0][0]
        prev_dt = flows[0][0]
        for dt, _ in flows:
            if dt <= as_of_dt:
                prev_dt = dt
            else:
                return prev_dt, dt
        return flows[-1][0], flows[-1][0]

    def forward_yield(self, today, underlying_bond, market_yield=None):
        if not underlying_bond:
            return None

        today = to_date(today)

        bond = KTB(
            underlying_bond.issue_date,
            underlying_bond.maturity_date,
            underlying_bond.coupon_rate,
        )
        flows = bond.cash_flows()

        if today < flows[0][0]:
            pymt_date1 = bond.issue
            pymt_date2 = flows[0][0]
        else:
            pymt_date1, pymt_date2 = self._adjacent_payment_dates(
                today, flows, bond.issue
            )

        # 채권 유통가격
        market_yield = underlying_bond.market_yield / 100
        remaining_count = sum(1 for dt, _ in flows if dt > today)
        underlying_bond_price = self.bond_market_price(
            market_yield,
            bond.coupon,
            pymt_date1,
            pymt_date2,
            today,
            remaining_count,
        )

        # 선물 만기일
        futures_expiry, _ = futures_termination_date(today)

        # 선물 만기일 전 지급 될 쿠폰
        coupon_before_futures_expiry = sum(
            amt for dt, amt in flows if (today < dt <= futures_expiry)
        )

        if coupon_before_futures_expiry:
            pymt_date1, pymt_date2 = self._adjacent_payment_dates(
                futures_expiry, flows, bond.issue
            )
            days_until_pymt_date = (pymt_date1 - today).days
            coupon_before_futures_expiry /= (
                1 + self.params.cd91 * days_until_pymt_date / 365
            )

        clean_price = underlying_bond_price - coupon_before_futures_expiry
        days_until_futures_expiry = (futures_expiry - today).days

        # Forward Dirty Price
        fwd_price = clean_price * (
            1 + self.params.cd91 * days_until_futures_expiry / 365
        )

        # Equation at futures expiry
        num_at_expiry = sum(1 for dt, _ in flows if dt >= futures_expiry)
        equation_fwd_price = self.bond_market_price(
            Symbol("y"),
            bond.coupon,
            pymt_date1,
            pymt_date2,
            futures_expiry,
            num_at_expiry,
        )

        # Implied Yield
        try:
            return float(nsolve(equation_fwd_price - fwd_price, 0))
        except Exception:
            raise Exception("Failed to solve for forward yield")

    def fair_value(self, tenor):
        basket = self.params.basket(tenor)
        fwd_yields = [
            y
            for y in [
                self.forward_yield(self.params.today, basket.underlying1),
                self.forward_yield(self.params.today, basket.underlying2),
                self.forward_yield(self.params.today, basket.underlying3),
            ]
            if y is not None
        ]
        avg_yield = sum(map(float, fwd_yields)) / len(fwd_yields)

        pv_coupons = sum(
            2.5 / (1 + avg_yield / 2) ** i for i in range(1, 2 * tenor + 1)
        )
        pv_redemption = 100 / (1 + avg_yield / 2) ** (2 * tenor)
        return float(pv_coupons + pv_redemption)

    def bond_market_price(
        self,
        y,
        coupon_rate_pct,
        pymt_date1: datetime,
        pymt_date2: datetime,
        pricing_date: datetime,
        num_pymt: int,
    ):
        """
        Price on pricing_date for a 10,000 par bond given an annual yield 'y' (can be sympy Symbol).
        Uses semiannual comp with simple day fraction adjustment to valuation date.
        """
        face = 10000.0
        coupon_amt = face * (coupon_rate_pct / 2) / 100.0

        price = 0.0
        for i in range(num_pymt):
            price += coupon_amt / (1 + y / 2) ** i
        price += face / (1 + y / 2) ** i  # i == num_pymt - 1

        d = (pymt_date2 - pricing_date).days
        t = max((pymt_date2 - pymt_date1).days, 1)
        expr = price / (1 + (d / t) * (y / 2))
        try:
            return float(expr)  # numeric branch
        except TypeError:
            return expr  # symbolic branch for nsolve
