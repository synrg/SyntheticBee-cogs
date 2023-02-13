"""Dictionary cog for Red-DiscordBot based on Wiktionary."""
from redbot.core import commands
from wiktionaryparser import WiktionaryParser


class WDict(commands.Cog):
    """Look up word definitions from Wiktionary."""

    __author__ = "SyntheticBee"

    @commands.command(aliases=["wiktionary"])
    async def wdict(self, ctx: commands.Context, *, query: str):
        """Look up word definitions from Wiktionary."""
        parser = WiktionaryParser()
        words = parser.fetch(query, "english")
        page = ""
        nl = "\n"
        for entry in words:
            for definition in entry["definitions"]:
                t = definition["text"]
                p = definition["partOfSpeech"]
                page += f"{p}: {t[0]}{nl}"
                index = 0
                for sense in t[1:]:
                    index += 1
                    page += f"{index}. {sense}{nl}"
                page += nl
        if not page:
            page = "No definitions found"
        await ctx.send(page)
