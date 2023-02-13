"""WDict init."""
from redbot.core.bot import Red
from redbot.core.utils import get_end_user_data_statement

from .wdict import WDict

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: Red) -> None:
    """Load Wiktionary cog."""
    cog = WDict()
    r = bot.add_cog(cog)
    if r is not None:
        await r
