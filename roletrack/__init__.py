"""WDict init."""
from redbot.core.bot import Red
from redbot.core.utils import get_end_user_data_statement

from .roletrack import RoleTrack

__red_end_user_data_statement__ = get_end_user_data_statement(__file__)


async def setup(bot: Red) -> None:
    """Load RoleTrack cog."""
    await bot.add_cog(RoleTrack(bot))
