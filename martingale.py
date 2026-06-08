import json
import logging
from pathlib import Path
from typing import Dict, Optional
import config

logger = logging.getLogger(__name__)


class MartingaleManager:
    """
    Manages Martingale staking: $2 → $4 → $8 → $16 → $32
    - On win: reset to base stake
    - On loss: double stake
    - Hit level 5 and lose: reset to base and continue
    """

    def __init__(self):
        self.current_level = 1  # 1-5
        self.total_wins = 0
        self.total_losses = 0
        self.net_pnl = 0.0
        self.trades_history = []
        self.state_file = config.STATE_DIR / "martingale_state.json"
        self.load_state()

    def get_stake(self, level: Optional[int] = None) -> float:
        """Get stake amount for given level (1-5), default to current level."""
        if level is None:
            level = self.current_level

        if level < 1 or level > config.MAX_MARTINGALE_LEVEL:
            raise ValueError(f"Level must be 1-{config.MAX_MARTINGALE_LEVEL}")

        return config.MARTINGALE_STAKES[level - 1]

    def record_win(self, stake: float, pnl: float) -> Dict:
        """Record a winning trade and reset to base level."""
        self.total_wins += 1
        self.net_pnl += pnl

        trade = {
            'level': self.current_level,
            'type': 'WIN',
            'stake': stake,
            'pnl': pnl,
            'new_level': 1,
        }

        self.trades_history.append(trade)
        self.current_level = 1

        logger.info(f"✅ WIN at level {trade['level']} | Stake: ${stake:.2f} | P&L: ${pnl:.2f} | Reset to Level 1")
        self.save_state()

        return trade

    def record_loss(self, stake: float, loss: float) -> Dict:
        """Record a losing trade and advance Martingale level."""
        self.total_losses += 1
        self.net_pnl -= loss

        old_level = self.current_level

        # If at max level, reset to 1; otherwise double
        if self.current_level >= config.MAX_MARTINGALE_LEVEL:
            self.current_level = 1
            reset_msg = "| MAX LEVEL HIT - Reset to Level 1"
        else:
            self.current_level += 1
            reset_msg = f"| Advancing to Level {self.current_level}"

        trade = {
            'level': old_level,
            'type': 'LOSS',
            'stake': stake,
            'loss': loss,
            'new_level': self.current_level,
        }

        self.trades_history.append(trade)

        logger.warning(f"❌ LOSS at level {old_level} | Stake: ${stake:.2f} | Loss: ${loss:.2f} | Next stake: ${self.get_stake():.2f} {reset_msg}")
        self.save_state()

        return trade

    def get_next_stake(self) -> float:
        """Get the stake for the next trade."""
        return self.get_stake(self.current_level)

    def get_stats(self) -> Dict:
        """Get trading statistics."""
        total_trades = self.total_wins + self.total_losses

        return {
            'current_level': self.current_level,
            'current_stake': self.get_stake(),
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'total_trades': total_trades,
            'win_rate': (self.total_wins / total_trades * 100) if total_trades > 0 else 0,
            'net_pnl': self.net_pnl,
            'avg_win': self.net_pnl / self.total_wins if self.total_wins > 0 else 0,
        }

    def save_state(self) -> None:
        """Save state to JSON file."""
        state = {
            'current_level': self.current_level,
            'total_wins': self.total_wins,
            'total_losses': self.total_losses,
            'net_pnl': self.net_pnl,
            'trades_history': self.trades_history,
        }

        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_state(self) -> None:
        """Load state from JSON file if it exists."""
        if not self.state_file.exists():
            logger.info("No previous state found, starting fresh")
            return

        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.current_level = state.get('current_level', 1)
                self.total_wins = state.get('total_wins', 0)
                self.total_losses = state.get('total_losses', 0)
                self.net_pnl = state.get('net_pnl', 0.0)
                self.trades_history = state.get('trades_history', [])
            logger.info(f"Loaded previous state: Level {self.current_level}, W/L: {self.total_wins}/{self.total_losses}")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def reset(self) -> None:
        """Reset all stats to initial state."""
        self.current_level = 1
        self.total_wins = 0
        self.total_losses = 0
        self.net_pnl = 0.0
        self.trades_history = []
        self.save_state()
        logger.info("Martingale state reset")

    def get_history(self, limit: int = 10) -> list:
        """Get recent trade history."""
        return self.trades_history[-limit:]
