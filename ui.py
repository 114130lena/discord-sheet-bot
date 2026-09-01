import asyncio
import discord

SHEET_URL = "https://docs.google.com/spreadsheets/d/1FARr4g1gNM1P9oaFvpFSd3xWJo1BtgBy9398WwlzU8M/edit?usp=sharing"


def project_embed(project):
    teams = project.get("teams", [])
    embed = discord.Embed(title="📊 전력분석 결과", description=f"총 **{len(teams)}팀**\nAI 추출 결과를 확인하고 수정한 뒤 저장하세요.")
    for index, team in enumerate(teams, 1):
        name = team.get("team_name", "")
        tag = team.get("team_tag", "")
        title = f"{name} [{tag}]" if name and tag else (name or tag or f"팀 {index}")
        try:
            roster_size = int(team.get("roster_size", 4))
        except Exception:
            roster_size = 4
        players = [team.get(f"player{i}", "") for i in range(1, 5)]
        players = players[:3] if roster_size == 3 else players
        text = "\n".join(f"{i}. {p or '-'}" for i, p in enumerate(players, 1)) or "-"
        note = team.get("notes", "")
        if note:
            text += f"\n📝 {note}"
        embed.add_field(name=f"{index}. {title}", value=text, inline=True)

    identities = project.get("player_identities", {})
    unresolved = sum(1 for item in identities.values() if not item.get("game_nick"))
    suggestions = project.get("db_suggestions", {})
    parts = []
    if unresolved:
        parts.append(f"🎮 인게임닉 미확인 {unresolved}명")
    if suggestions.get("teams"):
        parts.append(f"🆕 신규 팀 {len(suggestions['teams'])}개")
    if suggestions.get("players"):
        parts.append(f"🆕 신규 선수 {len(suggestions['players'])}명")
    if suggestions.get("transfers"):
        parts.append(f"🔄 이적 의심 {len(suggestions['transfers'])}건")
    if parts:
        embed.set_footer(text=" / ".join(parts) + " · 닉네임 구분과 전적 분석은 아래 버튼에서 할 수 있습니다.")
    return embed


def _project_player_names(project):
    names = []
    seen = set()
    for team in project.get("teams", []):
        for index in range(1, 5):
            name = str(team.get(f"player{index}", "")).strip()
            if name and name != "[확인 필요]" and name not in seen:
                seen.add(name)
                names.append(name)
    return names


async def _call_callback(callback, *args):
    if callback is None:
        raise RuntimeError("callback is not connected")
    result = callback(*args)
    if hasattr(result, "__await__"):
        result = await result
    return result


class TeamEditModal(discord.ui.Modal):
    def __init__(self, project, index, parent_view):
        super().__init__(title="팀 정보 수정")
        self.project = project
        self.index = index
        self.parent_view = parent_view
        team = project["teams"][index]
        self.team_name = discord.ui.TextInput(label="팀명", default=team.get("team_name", ""), required=False, max_length=100)
        self.team_tag = discord.ui.TextInput(label="약칭", default=team.get("team_tag", ""), required=False, max_length=30)
        self.roster = discord.ui.TextInput(label="로스터 인원 (3 또는 4)", default=str(team.get("roster_size", 4)), required=True, max_length=1)
        players = "\n".join(team.get(f"player{i}", "") for i in range(1, 5) if team.get(f"player{i}", ""))
        self.players = discord.ui.TextInput(label="선수 (한 줄에 한 명)", default=players, required=False, max_length=300, style=discord.TextStyle.paragraph)
        self.notes = discord.ui.TextInput(label="팀 메모", default=team.get("notes", ""), required=False, max_length=500, style=discord.TextStyle.paragraph)
        for item in (self.team_name, self.team_tag, self.roster, self.players, self.notes):
            self.add_item(item)

    async def on_submit(self, interaction):
        roster = self.roster.value.strip()
        if roster not in {"3", "4"}:
            await interaction.response.send_message("❌ 로스터 인원은 3 또는 4만 입력할 수 있습니다.", ephemeral=True)
            return
        team = self.project["teams"][self.index]
        names = [x.strip() for x in self.players.value.splitlines() if x.strip()][:4]
        team["team_name"] = self.team_name.value.strip()
        team["team_tag"] = self.team_tag.value.strip()
        team["roster_size"] = int(roster)
        for i in range(1, 5):
            team[f"player{i}"] = names[i - 1] if i <= len(names) and i <= int(roster) else ""
        team["notes"] = self.notes.value.strip()
        await interaction.response.edit_message(content="📊 **전력분석 결과**", embed=project_embed(self.project), view=self.parent_view)


class AddTeamModal(discord.ui.Modal):
    def __init__(self, project, parent_view):
        super().__init__(title="팀 추가")
        self.project = project
        self.parent_view = parent_view
        self.team_name = discord.ui.TextInput(label="팀명", required=False, max_length=100)
        self.team_tag = discord.ui.TextInput(label="약칭", required=False, max_length=30)
        self.roster = discord.ui.TextInput(label="로스터 인원 (3 또는 4)", default="4", required=True, max_length=1)
        self.players = discord.ui.TextInput(label="선수 (한 줄에 한 명)", required=False, max_length=300, style=discord.TextStyle.paragraph)
        self.notes = discord.ui.TextInput(label="팀 메모", required=False, max_length=500, style=discord.TextStyle.paragraph)
        for item in (self.team_name, self.team_tag, self.roster, self.players, self.notes):
            self.add_item(item)

    async def on_submit(self, interaction):
        roster = self.roster.value.strip()
        if roster not in {"3", "4"}:
            await interaction.response.send_message("❌ 로스터 인원은 3 또는 4만 입력할 수 있습니다.", ephemeral=True)
            return
        names = [x.strip() for x in self.players.value.splitlines() if x.strip()][:4]
        team = {
            "team_name": self.team_name.value.strip(),
            "team_tag": self.team_tag.value.strip(),
            "roster_size": int(roster),
            "player1": names[0] if len(names) > 0 else "",
            "player2": names[1] if len(names) > 1 else "",
            "player3": names[2] if len(names) > 2 else "",
            "player4": names[3] if len(names) > 3 and int(roster) >= 4 else "",
            "experiment1": "",
            "experiment2": "",
            "experiment3": "",
            "experiment4": "",
            "strategy": "",
            "combat_points": "",
            "notes": self.notes.value.strip(),
        }
        self.project.setdefault("teams", []).append(team)
        await interaction.response.edit_message(content="📊 **전력분석 결과**", embed=project_embed(self.project), view=self.parent_view)


class TeamSelect(discord.ui.Select):
    def __init__(self, project, parent_view):
        self.project = project
        self.parent_view = parent_view
        options = []
        for i, team in enumerate(project.get("teams", [])):
            label = team.get("team_name") or team.get("team_tag") or f"팀 {i + 1}"
            options.append(discord.SelectOption(label=label[:100], value=str(i)))
        if not options:
            options = [discord.SelectOption(label="팀 없음", value="-1")]
        super().__init__(placeholder="수정할 팀 선택", options=options[:25])

    async def callback(self, interaction):
        index = int(self.values[0])
        if index < 0:
            await interaction.response.send_message("❌ 수정할 팀이 없습니다.", ephemeral=True)
            return
        await interaction.response.send_modal(TeamEditModal(self.project, index, self.parent_view))


class DeleteTeamSelect(discord.ui.Select):
    def __init__(self, project, parent_view):
        self.project = project
        self.parent_view = parent_view
        options = []
        for i, team in enumerate(project.get("teams", [])):
            label = team.get("team_name") or team.get("team_tag") or f"팀 {i + 1}"
            options.append(discord.SelectOption(label=label[:100], value=str(i)))
        if not options:
            options = [discord.SelectOption(label="팀 없음", value="-1")]
        super().__init__(placeholder="삭제할 팀 선택", options=options[:25])

    async def callback(self, interaction):
        index = int(self.values[0])
        if index < 0:
            await interaction.response.send_message("❌ 삭제할 팀이 없습니다.", ephemeral=True)
            return
        self.project["teams"].pop(index)
        await interaction.response.edit_message(content="📊 **전력분석 결과**", embed=project_embed(self.project), view=self.parent_view)


class EditView(discord.ui.View):
    def __init__(self, project, parent_view):
        super().__init__(timeout=180)
        self.project = project
        self.parent_view = parent_view
        self.add_item(TeamSelect(project, parent_view))

    @discord.ui.button(label="➕ 팀 추가", style=discord.ButtonStyle.success)
    async def add_team(self, interaction, button):
        await interaction.response.send_modal(AddTeamModal(self.project, self.parent_view))

    @discord.ui.button(label="🗑️ 팀 삭제", style=discord.ButtonStyle.danger)
    async def delete_team(self, interaction, button):
        await interaction.response.edit_message(content="🗑️ **삭제할 팀을 선택하세요.**", embed=project_embed(self.project), view=DeleteTeamView(self.project, self.parent_view))

    @discord.ui.button(label="↩️ 돌아가기", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        await interaction.response.edit_message(content="📊 **전력분석 결과**", embed=project_embed(self.project), view=self.parent_view)


class DeleteTeamView(discord.ui.View):
    def __init__(self, project, parent_view):
        super().__init__(timeout=180)
        self.project = project
        self.parent_view = parent_view
        self.add_item(DeleteTeamSelect(project, parent_view))

    @discord.ui.button(label="↩️ 돌아가기", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        await interaction.response.edit_message(content="📊 **전력분석 결과**", embed=project_embed(self.project), view=self.parent_view)


class NicknameEntryModal(discord.ui.Modal):
    def __init__(self, project, parent_view):
        super().__init__(title="닉네임 종류 지정")
        self.project = project
        self.parent_view = parent_view
        self.player_name = discord.ui.TextInput(label="분석표에 표시된 선수 닉네임", placeholder="예: 굉가리", required=True, max_length=100)
        self.add_item(self.player_name)

    async def on_submit(self, interaction):
        name = self.player_name.value.strip()
        players = _project_player_names(self.project)
        if name not in players:
            await interaction.response.send_message("❌ 현재 전력분석 로스터에서 해당 닉네임을 찾지 못했습니다.", ephemeral=True)
            return
        await interaction.response.send_message(f"👤 **{name}**\n이 닉네임의 종류를 선택하세요.", view=NicknameTypeView(self.project, self.parent_view, name), ephemeral=True)


class TournamentNickModal(discord.ui.Modal):
    def __init__(self, project, parent_view, display_name):
        super().__init__(title="대회닉 → 인게임닉 연결")
        self.project = project
        self.parent_view = parent_view
        self.display_name = display_name
        self.game_nick = discord.ui.TextInput(label="실제 인게임 닉네임", placeholder="DAK.GG에서 검색되는 닉네임", required=True, max_length=100)
        self.add_item(self.game_nick)

    async def on_submit(self, interaction):
        game_nick = self.game_nick.value.strip()
        try:
            if self.parent_view.nickname_callback is not None:
                result = await _call_callback(self.parent_view.nickname_callback, self.project, self.display_name, "tournament", game_nick)
            else:
                from player_analysis import set_manual_game_nick
                from data import save_project
                result = await asyncio.to_thread(set_manual_game_nick, self.project, self.display_name, game_nick)
                await asyncio.to_thread(save_project, self.project)
        except Exception as e:
            await interaction.response.send_message(f"❌ 저장 실패: `{type(e).__name__}: {e}`", ephemeral=True)
            return
        await interaction.response.send_message(f"🏆 **대회닉으로 저장 완료**\n`{self.display_name}` → 🎮 `{result.get('game_nick', game_nick)}`\n다음 전체 전적분석부터 이 인게임 닉네임으로 DAK.GG를 조회합니다.", ephemeral=True)


class NicknameTypeView(discord.ui.View):
    def __init__(self, project, parent_view, display_name):
        super().__init__(timeout=180)
        self.project = project
        self.parent_view = parent_view
        self.display_name = display_name

    @discord.ui.button(label="🎮 인게임닉", style=discord.ButtonStyle.success)
    async def mark_in_game(self, interaction, button):
        try:
            if self.parent_view.nickname_callback is not None:
                result = await _call_callback(self.parent_view.nickname_callback, self.project, self.display_name, "in_game", None)
            else:
                from player_analysis import set_manual_in_game_nick
                from data import save_project
                result = await asyncio.to_thread(set_manual_in_game_nick, self.project, self.display_name)
                await asyncio.to_thread(save_project, self.project)
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ 저장 실패: `{type(e).__name__}: {e}`", view=None)
            return
        await interaction.response.edit_message(content=f"🎮 **인게임 닉네임으로 저장 완료**\n`{result.get('game_nick', self.display_name)}`을 그대로 DAK.GG 검색에 사용합니다.", view=None)

    @discord.ui.button(label="🏆 대회닉", style=discord.ButtonStyle.primary)
    async def mark_tournament(self, interaction, button):
        await interaction.response.send_modal(TournamentNickModal(self.project, self.parent_view, self.display_name))


class ProjectView(discord.ui.View):
    def __init__(self, project, save_callback=None, db_callback=None, nickname_callback=None, analyze_all_callback=None):
        super().__init__(timeout=300)
        self.project = project
        self.save_callback = save_callback
        self.db_callback = db_callback
        self.nickname_callback = nickname_callback
        self.analyze_all_callback = analyze_all_callback
        self.add_item(discord.ui.Button(label="📊 Google Sheets 열기", style=discord.ButtonStyle.link, url=SHEET_URL))

    @discord.ui.button(label="✏️ 수정", style=discord.ButtonStyle.primary)
    async def edit_button(self, interaction, button):
        await interaction.response.edit_message(content="✏️ **수정할 팀을 선택하세요.**", embed=project_embed(self.project), view=EditView(self.project, self))

    @discord.ui.button(label="🎮 닉네임 구분", style=discord.ButtonStyle.primary)
    async def nickname_button(self, interaction, button):
        await interaction.response.send_modal(NicknameEntryModal(self.project, self))

    @discord.ui.button(label="📈 전체 전적 분석", style=discord.ButtonStyle.success)
    async def analyze_all_button(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if self.analyze_all_callback is not None:
                results = await _call_callback(self.analyze_all_callback, self.project)
            else:
                from player_analysis import analyze_all_players
                from data import save_project
                results = await asyncio.to_thread(analyze_all_players, self.project, 3, True)
                await asyncio.to_thread(save_project, self.project)
        except Exception as e:
            await interaction.followup.send(f"❌ 전체 전적 분석 실패: `{type(e).__name__}: {e}`", ephemeral=True)
            return

        success = []
        unresolved = []
        failed = []
        for name, result in results.items():
            status = result.get("status")
            if status == "ok":
                chars = result.get("characters", [])
                if chars:
                    top_text = ", ".join(f"{i + 1}. {item.get('name', '-')} {item.get('games', 0)}판" for i, item in enumerate(chars[:3]))
                else:
                    top_text = "실험체 데이터 없음"
                success.append(f"🎮 **{name}** → `{result.get('game_nick', '-')}`\n{top_text}")
            elif status == "manual_required":
                unresolved.append(name)
            else:
                failed.append(f"{name} ({result.get('error') or result.get('status') or '조회 실패'})")

        summary = f"📈 **전체 전적 분석 완료**\n성공 **{len(success)}명** · 닉네임 확인 필요 **{len(unresolved)}명** · 조회 실패 **{len(failed)}명**"
        if unresolved:
            summary += "\n\n⚠️ 닉네임 확인 필요: " + ", ".join(unresolved[:20])
        if failed:
            summary += "\n❌ 조회 실패: " + "\n".join(failed[:10])

        chunks = []
        current = summary
        for block in success:
            addition = "\n\n" + block
            if len(current) + len(addition) > 1800:
                chunks.append(current)
                current = block
            else:
                current += addition
        chunks.append(current)
        await interaction.followup.send(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)

    @discord.ui.button(label="🧠 DB 반영", style=discord.ButtonStyle.secondary)
    async def db_button(self, interaction, button):
        if self.db_callback is None:
            await interaction.response.send_message("❌ DB 기능이 연결되지 않았습니다.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            result = await _call_callback(self.db_callback, self.project)
            for child in self.children:
                if getattr(child, "label", "") == "🧠 DB 반영":
                    child.disabled = True
            await interaction.edit_original_response(content=f"🧠 **DB 반영 완료.**\n신규 팀 {result.get('teams', 0)}개 · 신규 선수 {result.get('players', 0)}명 · 이적 {result.get('transfers', 0)}건\n💾 반영 전 DB 백업도 생성했습니다.", embed=project_embed(self.project), view=self)
        except Exception as e:
            print(f"DB 반영 오류: {e}")
            await interaction.edit_original_response(content=f"❌ **DB 반영 실패:** `{type(e).__name__}: {e}`", embed=project_embed(self.project), view=self)

    @discord.ui.button(label="💾 시트에 저장", style=discord.ButtonStyle.success)
    async def save_button(self, interaction, button):
        if self.save_callback is None:
            await interaction.response.send_message("❌ 저장 기능이 연결되지 않았습니다.", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            await _call_callback(self.save_callback, self.project)
            await interaction.edit_original_response(content="✅ **Google Sheets 저장 완료.**\n아래 버튼으로 시트를 열 수 있습니다.", embed=project_embed(self.project), view=self)
        except Exception as e:
            print(f"Google Sheets 저장 오류: {e}")
            await interaction.edit_original_response(content=f"❌ **저장 실패:** `{type(e).__name__}`", embed=project_embed(self.project), view=self)

    @discord.ui.button(label="❌ 닫기", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction, button):
        try:
            await interaction.response.defer()
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            try:
                await interaction.response.edit_message(content="🛑 **전력분석 결과를 닫았습니다.**", view=None)
            except Exception:
                pass
        except Exception as e:
            print(f"결과 메시지 삭제 오류: {e}")
