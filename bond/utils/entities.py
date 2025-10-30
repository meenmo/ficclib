from typing import Optional
from dataclasses import dataclass

@dataclass
class Bond:
    issue_date: str
    maturity_date: str
    coupon_rate: float
    market_yield: float
    isin: str = ""

@dataclass
class Basket:
    today: str = ""
    tenor: int = 0
    product_code: str = ""
    market_price: float = 0.0
    underlying1: Optional[Bond] = None
    underlying2: Optional[Bond] = None
    underlying3: Optional[Bond] = None