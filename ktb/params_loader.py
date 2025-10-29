import pandas as pd

from config.database import DatabaseEngine
from ficclib.utils.date import to_date
from ficclib.utils.entities import Basket, Bond


class FuturesParams:
    def __init__(self, today):
        self.today = today
        self.cd91 = self.load_cd91()

    def engine(self):
        return DatabaseEngine.get_mysql_engine()

    def load_cd91(self):
        query = "SELECT `CD` FROM `단기금리` WHERE Date = %s"
        df = pd.read_sql(query, self.engine(), params=(self.today,))
        return df.iloc[0].item() / 100

    def load_basket_data(self, tenor):
        query = "SELECT * FROM `KTB_Futures_%sY` WHERE Date = %s AND `근월물` = 'Y'"
        return pd.read_sql(query, self.engine(), params=(tenor, self.today))

    def basket(self, tenor):
        basket = Basket()
        df = self.load_basket_data(tenor)
        basket.today = to_date(self.today)
        basket.tenor = tenor
        basket.product_code = df["선물코드"].iloc[0]
        basket.market_price = df["시장가"].iloc[0]

        basket.underlying1 = Bond(
            issue_date=df["발행일1"].iloc[0],
            maturity_date=df["만기일1"].iloc[0],
            coupon_rate=df["표면금리1"].iloc[0],
            market_yield=df["기초채권1_민평3사금리"].iloc[0],
            isin=df["기초채권1"].iloc[0],
        )

        basket.underlying2 = Bond(
            issue_date=df["발행일2"].iloc[0],
            maturity_date=df["만기일2"].iloc[0],
            coupon_rate=df["표면금리2"].iloc[0],
            market_yield=df["기초채권2_민평3사금리"].iloc[0],
            isin=df["기초채권2"].iloc[0],
        )

        if "기초채권3" in df.columns:
            basket.underlying3 = Bond(
                issue_date=df["발행일3"].iloc[0],
                maturity_date=df["만기일3"].iloc[0],
                coupon_rate=df["표면금리3"].iloc[0],
                market_yield=df["기초채권3_민평3사금리"].iloc[0],
                isin=df["기초채권3"].iloc[0],
            )

        return basket
