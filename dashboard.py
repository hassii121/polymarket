import logging
import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from bot import PolymarketBot

logger = logging.getLogger(__name__)
console = Console()


class Dashboard:
    """
    Terminal dashboard displaying:
    - Real-time signal scores
    - Martingale level and stake
    - Trade history and P&L
    - Window countdown
    - Active orders
    """

    def __init__(self, bot: "PolymarketBot"):
        self.bot = bot
        self.update_interval = 1  # Update every 1 second

    def get_header(self) -> Panel:
        """Create header panel."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = Text("🤖 POLYMARKET BTC 5-MIN TRADING BOT", style="bold blue")
        subtitle = Text(f"Last updated: {now}", style="dim")

        return Panel(
            Text.assemble(title, "\n", subtitle),
            border_style="blue",
        )

    def get_signal_panel(self) -> Panel:
        """Create signal analysis panel."""
        signal = self.bot.last_signal

        if not signal or not signal.get('ready'):
            content = Text("⏳ Waiting for signal data...", style="dim yellow")
            return Panel(content, title="📊 Signal Analysis", border_style="yellow")

        score = signal.get('score', 0)
        direction = signal.get('direction', 'UNKNOWN')
        confidence = signal.get('confidence', 'UNKNOWN')
        components = signal.get('components', {})

        # Color based on score
        if score > 70:
            color = "green"
            indicator = "🟢"
        elif score < 30:
            color = "red"
            indicator = "🔴"
        else:
            color = "yellow"
            indicator = "🟡"

        content_lines = [
            f"{indicator} Direction: {Text(direction, style=f'bold {color}')}",
            f"   Score: {score:.1f}/100 ({confidence})",
            "",
            "Component Scores:",
            f"   TA (RSI/MACD/EMA):     {components.get('ta', 0):.1f}%",
            f"   Funding Rate:           {components.get('funding_rate', 0):.1f}%",
            f"   Fear & Greed Index:     {components.get('fear_greed', 0):.1f}%",
            f"   Order Book Imbalance:   {components.get('orderbook', 0):.1f}%",
        ]

        content = Text("\n".join(content_lines), style="")
        return Panel(content, title="📊 Signal Analysis", border_style="cyan")

    def get_martingale_panel(self) -> Panel:
        """Create Martingale state panel."""
        stats = self.bot.martingale.get_stats()

        level = stats['current_level']
        stake = stats['current_stake']
        wins = stats['total_wins']
        losses = stats['total_losses']
        total = stats['total_trades']
        wr = stats['win_rate']
        pnl = stats['net_pnl']

        # PnL color
        pnl_color = "green" if pnl >= 0 else "red"
        pnl_symbol = "📈" if pnl >= 0 else "📉"

        level_indicator = "🔼" if level < 5 else "🔥"

        content_lines = [
            f"{level_indicator} Current Level: {level}/5 → Next Stake: ${stake:.2f}",
            "",
            f"Win Rate: {wins}W / {losses}L ({wr:.1f}%) | Total: {total}",
            f"{pnl_symbol} Net P&L: {Text(f'${pnl:.2f}', style=pnl_color)}",
        ]

        content = Text("\n".join(content_lines))
        return Panel(content, title="💰 Martingale State", border_style="magenta")

    def get_window_panel(self) -> Panel:
        """Create window countdown panel."""
        seconds = self.bot.get_current_window_seconds()
        countdown = self.bot.get_window_countdown()
        in_entry_window = seconds >= 240

        entry_status = "🎯 IN ENTRY WINDOW" if in_entry_window else "⏳ Waiting..."
        entry_color = "bold green" if in_entry_window else "dim"

        content_lines = [
            f"{entry_status}",
            f"   Time in window: {seconds}s / 300s",
            f"   Countdown to close: {countdown}s",
            "",
            f"Entry Window: 240-300s (last 60s)",
            f"Signal Threshold: {420} / 100", # MIN_SIGNAL_SCORE
        ]

        content = Text("\n".join(content_lines))
        return Panel(content, title="⏱️  Window Timing", border_style="cyan")

    def get_order_panel(self) -> Panel:
        """Create active orders panel."""
        pending = self.bot.pending_order

        if not pending:
            content = Text("✅ No pending orders", style="dim green")
            return Panel(content, title="📋 Active Orders", border_style="green")

        direction = pending['direction']
        stake = pending['stake']
        level = pending['level']
        elapsed = time.time() - pending['timestamp']

        order_icon = "📈" if direction == 'UP' else "📉"

        content_lines = [
            f"{order_icon} {direction} Order",
            f"   Stake: ${stake:.2f} (Level {level})",
            f"   Placed: {elapsed:.0f}s ago",
            f"   ID: {pending['order_id'][:16]}...",
        ]

        content = Text("\n".join(content_lines))
        return Panel(content, title="📋 Active Orders", border_style="yellow")

    def get_trades_panel(self) -> Panel:
        """Create recent trades panel."""
        history = self.bot.martingale.get_history(limit=5)

        if not history:
            content = Text("No trades yet", style="dim")
            return Panel(content, title="📜 Recent Trades", border_style="white")

        table = Table(show_header=True, header_style="bold white")
        table.add_column("Lvl", style="cyan", width=3)
        table.add_column("Type", style="cyan", width=6)
        table.add_column("Stake", style="cyan", width=8)
        table.add_column("Result", style="cyan", width=10)

        for trade in reversed(history):
            level = str(trade['level'])
            trade_type = trade['type']
            stake = f"${trade['stake']:.2f}"

            if trade['type'] == 'WIN':
                pnl = trade['pnl']
                result_text = Text(f"+${pnl:.2f}", style="bold green")
            else:
                loss = trade['loss']
                result_text = Text(f"-${loss:.2f}", style="bold red")

            table.add_row(level, trade_type, stake, result_text)

        return Panel(table, title="📜 Recent Trades", border_style="white")

    def get_layout(self) -> Layout:
        """Create dashboard layout."""
        layout = Layout()

        layout.split(
            Layout(self.get_header(), name="header", size=3),
            Layout(name="main"),
        )

        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )

        layout["left"].split(
            Layout(self.get_signal_panel(), name="signal"),
            Layout(self.get_window_panel(), name="window"),
            Layout(self.get_order_panel(), name="order"),
        )

        layout["right"].split(
            Layout(self.get_martingale_panel(), name="martingale"),
            Layout(self.get_trades_panel(), name="trades"),
        )

        return layout

    async def display_loop(self):
        """Live update display."""
        try:
            with Live(self.get_layout(), refresh_per_second=1, console=console):
                while self.bot.running:
                    await asyncio.sleep(self.update_interval)
        except Exception as e:
            logger.error(f"Dashboard error: {e}")

    def print_startup_banner(self):
        """Print startup banner."""
        banner = """
╔════════════════════════════════════════════════════════════╗
║         🤖 POLYMARKET BTC 5-MIN TRADING BOT 🤖           ║
║                                                             ║
║  Strategy: Martingale ($2→$32, 5 levels)                  ║
║  Signal: TA (40%) + Funding (30%) + Fear (20%) + OB (10%) ║
║  Pair: BTC/USDT | Timeframe: 1m | Windows: 5m             ║
║  Network: Polygon | Settlement: USDC                       ║
║                                                             ║
╚════════════════════════════════════════════════════════════╝
        """
        console.print(banner, style="bold blue")
