from dataclasses import dataclass

@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    effective_risk_fraction: float

@dataclass(frozen=True)
class RiskPolicy:
    trade_risk_fraction: float = 0.005
    daily_loss_limit: float = 0.02
    weekly_loss_limit: float = 0.05
    max_consecutive_losses: int = 3
    def __post_init__(self):
        if not 0 < self.trade_risk_fraction <= 0.01: raise ValueError('trade risk must be >0 and <=1%')
        if not 0 < self.daily_loss_limit < 1 or not 0 < self.weekly_loss_limit < 1: raise ValueError('loss limits must be between 0 and 1')
        if self.max_consecutive_losses < 1: raise ValueError('max_consecutive_losses must be >=1')
    def evaluate(self, daily_loss_fraction: float = 0.0, weekly_loss_fraction: float = 0.0, consecutive_losses: int = 0, kill_switch: bool = False) -> RiskDecision:
        if kill_switch: return RiskDecision(False, 'kill_switch_active', 0.0)
        if daily_loss_fraction >= self.daily_loss_limit: return RiskDecision(False, 'daily_loss_limit_reached', 0.0)
        if weekly_loss_fraction >= self.weekly_loss_limit: return RiskDecision(False, 'weekly_loss_limit_reached', 0.0)
        if consecutive_losses >= self.max_consecutive_losses: return RiskDecision(False, 'consecutive_loss_pause', 0.0)
        return RiskDecision(True, 'approved', self.trade_risk_fraction)
