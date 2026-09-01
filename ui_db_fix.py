import discord

from data import find_player_match, save_project
from ui import ProjectView as BaseProjectView, project_embed


class DBFixProjectView(BaseProjectView):
    """Project UI with a manual DB typo-correction action."""

    @discord.ui.button(label="🔤 DB 오타 보정", style=discord.ButtonStyle.primary)
    async def db_typo_fix_button(self, interaction, button):
        corrected = []
        skipped = 0

        for team in self.project.get("teams", []):
            team_name = str(team.get("team_name", "")).strip()
            try:
                roster_size = int(team.get("roster_size", 4))
            except Exception:
                roster_size = 4

            for index in range(1, min(roster_size, 4) + 1):
                key = f"player{index}"
                original = str(team.get(key, "")).strip()
                if not original or original == "[확인 필요]":
                    continue

                match = find_player_match(original, team_hint=team_name)
                if not match:
                    skipped += 1
                    continue

                canonical = str(match["player"].get("name", original)).strip()
                if canonical and canonical != original:
                    team[key] = canonical
                    corrected.append({
                        "before": original,
                        "after": canonical,
                        "score": match.get("score", 0),
                    })

        save_project(self.project)

        if corrected:
            preview = "\n".join(
                f"• `{item['before']}` → **{item['after']}**"
                for item in corrected[:10]
            )
            extra = "" if len(corrected) <= 10 else f"\n… 외 {len(corrected) - 10}건"
            content = (
                f"🔤 **DB 오타 보정 완료!** {len(corrected)}개 이름을 수정했습니다.\n"
                f"{preview}{extra}"
            )
        else:
            content = "🔤 **DB 오타 보정 완료.** 자동으로 확정할 수 있는 이름은 없었습니다."
            if skipped:
                content += "\n비슷한 후보가 여러 개이거나 신뢰도가 낮은 이름은 그대로 유지했습니다."

        await interaction.response.edit_message(
            content=content,
            embed=project_embed(self.project),
            view=self,
        )
