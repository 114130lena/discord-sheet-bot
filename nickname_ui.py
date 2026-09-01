import discord

from data import save_project
from player_analysis import set_manual_game_nick


def _player_options(project):
    options = []
    seen = set()
    for team_index, team in enumerate(project.get("teams", []), 1):
        team_name = str(team.get("team_name") or team.get("team_tag") or f"팀 {team_index}").strip()
        try:
            roster_size = int(team.get("roster_size", 4))
        except Exception:
            roster_size = 4
        for player_index in range(1, min(roster_size, 4) + 1):
            name = str(team.get(f"player{player_index}", "")).strip()
            if not name or name == "[확인 필요]" or name in seen:
                continue
            seen.add(name)
            options.append(
                discord.SelectOption(
                    label=name[:100],
                    description=f"{team_name} · player{player_index}"[:100],
                    value=name,
                )
            )
    return options


class TournamentNickModal(discord.ui.Modal):
    def __init__(self, project, display_name, return_view):
        super().__init__(title="대회닉 → 인게임닉 연결")
        self.project = project
        self.display_name = display_name
        self.return_view = return_view
        self.game_nick = discord.ui.TextInput(
            label="DAK.GG에서 검색할 인게임 닉네임",
            placeholder="예: 실제 인게임 닉네임",
            required=True,
            max_length=60,
        )
        self.add_item(self.game_nick)

    async def on_submit(self, interaction):
        game_nick = self.game_nick.value.strip()
        set_manual_game_nick(self.project, self.display_name, game_nick)
        save_project(self.project)
        await interaction.response.edit_message(
            content=(
                "🏆 **대회닉으로 설정했습니다.**\n"
                f"`{self.display_name}` → 🎮 `{game_nick}`\n"
                "앞으로 전적 검색은 인게임 닉네임으로 진행됩니다."
            ),
            embed=None,
            view=NicknameManagerView(self.project, self.return_view, selected_name=self.display_name),
        )


class NicknameSelect(discord.ui.Select):
    def __init__(self, project, parent_view):
        self.project = project
        self.parent_view = parent_view
        options = _player_options(project)
        if not options:
            options = [discord.SelectOption(label="선수 없음", value="")]
        super().__init__(
            placeholder="닉네임 종류를 설정할 선수를 선택하세요",
            options=options[:25],
        )

    async def callback(self, interaction):
        selected = self.values[0]
        if not selected:
            await interaction.response.send_message("❌ 설정할 선수가 없습니다.", ephemeral=True)
            return
        await interaction.response.edit_message(
            content=(
                f"🏷️ **닉네임 구분: {selected}**\n"
                "이 이름이 DAK.GG에서 바로 검색되는 **인게임닉**인지, "
                "대회에서만 사용하는 **대회닉**인지 선택하세요."
            ),
            embed=None,
            view=NicknameManagerView(self.project, self.parent_view, selected_name=selected),
        )


class NicknameManagerView(discord.ui.View):
    def __init__(self, project, parent_view, selected_name=None):
        super().__init__(timeout=300)
        self.project = project
        self.parent_view = parent_view
        self.selected_name = selected_name
        self.add_item(NicknameSelect(project, parent_view))

    def _selected_or_none(self):
        return str(self.selected_name or "").strip()

    @discord.ui.button(label="🎮 인게임닉으로 지정", style=discord.ButtonStyle.success)
    async def set_in_game(self, interaction, button):
        name = self._selected_or_none()
        if not name:
            await interaction.response.send_message("먼저 선수를 선택하세요.", ephemeral=True)
            return
        set_manual_game_nick(self.project, name, name)
        save_project(self.project)
        await interaction.response.edit_message(
            content=(
                "🎮 **인게임닉으로 설정했습니다.**\n"
                f"`{name}`을 그대로 DAK.GG 전적 검색에 사용합니다."
            ),
            embed=None,
            view=NicknameManagerView(self.project, self.parent_view, selected_name=name),
        )

    @discord.ui.button(label="🏆 대회닉으로 지정", style=discord.ButtonStyle.primary)
    async def set_tournament(self, interaction, button):
        name = self._selected_or_none()
        if not name:
            await interaction.response.send_message("먼저 선수를 선택하세요.", ephemeral=True)
            return
        await interaction.response.send_modal(TournamentNickModal(self.project, name, self.parent_view))

    @discord.ui.button(label="📋 현재 구분 확인", style=discord.ButtonStyle.secondary)
    async def show_current(self, interaction, button):
        identities = self.project.get("player_identities", {})
        lines = []
        for name in [option.value for option in _player_options(self.project)]:
            identity = identities.get(name, {})
            game_nick = identity.get("game_nick")
            if game_nick:
                if str(game_nick).strip().lower() == name.lower():
                    lines.append(f"• 🎮 **{name}** — 인게임닉")
                else:
                    lines.append(f"• 🏆 **{name}** → 🎮 **{game_nick}**")
            else:
                lines.append(f"• ❓ **{name}** — 미설정")
        text = "🏷️ **닉네임 구분 현황**\n" + ("\n".join(lines[:25]) or "등록된 선수가 없습니다.")
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="↩️ 분석 결과로", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        await interaction.response.edit_message(
            content="📊 **전력분석 결과**",
            embed=self.parent_view.project_embed_fn(self.project) if hasattr(self.parent_view, "project_embed_fn") else None,
            view=self.parent_view,
        )


class NicknameTypeMixin:
    @discord.ui.button(label="🏷️ 닉네임 구분", style=discord.ButtonStyle.primary, row=2)
    async def nickname_type_button(self, interaction, button):
        options = _player_options(self.project)
        if not options:
            await interaction.response.send_message("❌ 분석된 선수가 없습니다.", ephemeral=True)
            return
        view = NicknameManagerView(self.project, self)
        await interaction.response.edit_message(
            content=(
                "🏷️ **대회닉 / 인게임닉 구분**\n"
                "선수를 선택한 뒤 이 이름이 DAK.GG에서 바로 검색되는지 설정하세요.\n"
                "• 🎮 인게임닉: 현재 이름 그대로 전적 검색\n"
                "• 🏆 대회닉: 실제 인게임 닉네임을 따로 연결"
            ),
            embed=None,
            view=view,
        )
