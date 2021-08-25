import datetime

from dataclassy import dataclass


@dataclass(slots=True, frozen=True, kwargs=True, init=True)
class BitmexInstrument:
    symbol: str
    timestamp: datetime.datetime
    rootSymbol: str
    state: str
    typ: str
    listing: datetime.datetime
    front: datetime.datetime
    expiry: datetime.datetime
    settle: datetime.datetime
    listedSettle: datetime.datetime
    relistInterval: datetime.datetime
    inverseLeg: str
    sellLeg: str
    buyLeg: str
    optionStrikePcnt: float
    optionStrikeRound: float
    optionStrikePrice: float
    optionMultiplier: float
    positionCurrency: str
    underlying: str
    quoteCurrency: str
    underlyingSymbol: str
    reference: str
    referenceSymbol: str
    calcInterval: datetime.datetime
    publishInterval: datetime.datetime
    publishTime: datetime.datetime
    maxOrderQty: float
    maxPrice: float
    lotSize: float
    tickSize: float
    multiplier: float
    settlCurrency: str
    underlyingToPositionMultiplier: float
    underlyingToSettleMultiplier: float
    quoteToSettleMultiplier: float
    isQuanto: bool
    isInverse: bool
    initMargin: float
    maintMargin: float
    riskLimit: float
    riskStep: float
    limit: float
    capped: bool
    taxed: bool
    deleverage: bool
    makerFee: float
    takerFee: float
    settlementFee: float
    insuranceFee: float
    fundingBaseSymbol: str
    fundingQuoteSymbol: str
    fundingPremiumSymbol: str
    fundingTimestamp: datetime.datetime
    fundingInterval: datetime.datetime
    fundingRate: float
    indicativeFundingRate: float
    rebalanceTimestamp: datetime.datetime
    rebalanceInterval: datetime.datetime
    openingTimestamp: datetime.datetime
    closingTimestamp: datetime.datetime
    sessionInterval: datetime.datetime
    prevClosePrice: float
    limitDownPrice: float
    limitUpPrice: float
    bankruptLimitDownPrice: float
    bankruptLimitUpPrice: float
    prevTotalVolume: float
    totalVolume: float
    volume: float
    volume24h: float
    prevTotalTurnover: float
    totalTurnover: float
    turnover: float
    turnover24h: float
    homeNotional24h: float
    foreignNotional24h: float
    prevPrice24h: float
    vwap: float
    highPrice: float
    lowPrice: float
    lastPrice: float
    lastPriceProtected: float
    lastTickDirection: str
    lastChangePcnt: float
    bidPrice: float
    midPrice: float
    askPrice: float
    impactBidPrice: float
    impactMidPrice: float
    impactAskPrice: float
    hasLiquidity: bool
    openInterest: float
    openValue: float
    fairMethod: str
    fairBasisRate: float
    fairBasis: float
    fairPrice: float
    markMethod: str
    markPrice: float
    indicativeTaxRate: float
    indicativeSettlePrice: float
    optionUnderlyingPrice: float
    settledPriceAdjustmentRate: float
    settledPrice: float

    def __setitem__(self, floor_number, data):
        self._floors[floor_number] = data

    def __getitem__(self, floor_number):
        return self._floors[floor_number]

    def _update(self, data):
        for k, v in data.items():
            setattr(self, k, v)
