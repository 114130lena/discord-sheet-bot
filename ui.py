import discord

from sheets import update_spreadsheet


def team_text(
    team,
    index
):

    roster_size = team.get(
        "roster_size",
        4
    )

    players = [
        team.get("player1", ""),
        team.get("player2", ""),
        team.get("player3", "")
    ]

    if roster_size == 4:

        players.append(
            team.get("player4", "")
        )

    player_text = " / ".join(
        p for p in players if p
    )

    return (
        f"**{index + 1}. "
        f"{team['team_name']} "
        f"[{roster_size}인]**\n"
        f"👤 {player_text}\n"
        f"📝 {team.get('description', '없음')}"
    )


def project_embed(
    project
):

    embed = discord.Embed(
        title="📋 팀 명단 분석 결과"
    )

    teams = project["teams"]

    if not teams:

        embed.description = (
            "현재 등록된 팀이 없습니다."
        )

        return embed

    text = ""

    for i, team in enumerate(
        teams
    ):

        text += team_text(
            team,
            i
        )

        text += "\n\n"

    if len(text) > 4000:

        text = (
            text[:3950]
            + "\n..."
        )

    embed.description = text

    embed.set_footer(
        text=f"총 {len(teams)}팀"
    )

    return embed


class ProjectView(
    discord.ui.View
):

    def __init__(
        self,
        project,
        save_callback
    ):

        super().__init__(
            timeout=1800
        )

        self.project = project
        self.save_callback = save_callback

    @discord.ui.button(
        label="✏️ 수정",
        style=discord.ButtonStyle.primary
    )
    async def edit_button(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "수정할 팀을 선택해주세요.",
            view=EditView(
                self.project,
                self.save_callback
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="👥 3↔4인",
        style=discord.ButtonStyle.primary
    )
    async def roster_button(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "로스터 인원을 변경할 팀을 선택해주세요.",
            view=RosterView(
                self.project,
                self.save_callback
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="➕ 팀 추가",
        style=discord.ButtonStyle.success
    )
    async def add_button(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            AddTeamModal(
                self.project,
                self.save_callback
            )
        )

    @discord.ui.button(
        label="🗑️ 팀 삭제",
        style=discord.ButtonStyle.danger
    )
    async def delete_button(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "삭제할 팀을 선택해주세요.",
            view=DeleteTeamView(
                self.project,
                self.save_callback
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="🔄 재분석",
        style=discord.ButtonStyle.secondary
    )
    async def reanalyze_button(
        self,
        interaction,
        button
    ):

        await interaction.response.send_message(
            "🔄 재분석 기능은 다음 단계에서 연결할게!",
            ephemeral=True
        )

    @discord.ui.button(
        label="✅ 확정",
        style=discord.ButtonStyle.success
    )
    async def confirm_button(
        self,
        interaction,
        button
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        try:

            url = create_spreadsheet(
                self.project
            )

            await interaction.followup.send(
                "🎉 **스프레드시트 생성 완료!**\n"
                f"📊 {url}",
                ephemeral=True
            )

        except Exception as e:

            print(
                f"Google Sheets 오류: {e}"
            )

            await interaction.followup.send(
                "❌ 스프레드시트 생성에 실패했어.\n"
                f"```text\n{e}\n```",
                ephemeral=True
            )

    @discord.ui.button(
        label="❌ 취소",
        style=discord.ButtonStyle.secondary
    )
    async def cancel_button(
        self,
        interaction,
        button
    ):

        await interaction.response.edit_message(
            content="❌ 작업이 취소되었습니다.",
            embed=None,
            view=None
        )


class EditView(
    discord.ui.View
):

    def __init__(
        self,
        project,
        save_callback
    ):

        super().__init__(
            timeout=300
        )

        options = []

        for i, team in enumerate(
            project["teams"][:25]
        ):

            options.append(
                discord.SelectOption(
                    label=(
                        f"{i + 1}. "
                        f"{team['team_name']}"
                    ),
                    value=str(i)
                )
            )

        if options:

            self.add_item(
                TeamSelect(
                    project,
                    save_callback,
                    options
                )
            )


class TeamSelect(
    discord.ui.Select
):

    def __init__(
        self,
        project,
        save_callback,
        options
    ):

        super().__init__(
            placeholder="수정할 팀 선택",
            options=options
        )

        self.project = project
        self.save_callback = save_callback

    async def callback(
        self,
        interaction
    ):

        index = int(
            self.values[0]
        )

        await interaction.response.send_modal(
            EditTeamModal(
                self.project,
                self.save_callback,
                index
            )
        )


class EditTeamModal(
    discord.ui.Modal
):

    def __init__(
        self,
        project,
        save_callback,
        index
    ):

        super().__init__(
            title="팀 정보 수정"
        )

        self.project = project
        self.save_callback = save_callback
        self.index = index

        team = project["teams"][index]

        self.team_name = discord.ui.TextInput(
            label="팀명",
            default=team.get(
                "team_name",
                ""
            ),
            required=True
        )

        self.player1 = discord.ui.TextInput(
            label="선수 1",
            default=team.get(
                "player1",
                ""
            ),
            required=False
        )

        self.player2 = discord.ui.TextInput(
            label="선수 2",
            default=team.get(
                "player2",
                ""
            ),
            required=False
        )

        self.player3 = discord.ui.TextInput(
            label="선수 3",
            default=team.get(
                "player3",
                ""
            ),
            required=False
        )

        self.player4 = discord.ui.TextInput(
            label="선수 4",
            default=team.get(
                "player4",
                ""
            ),
            required=False
        )

        self.add_item(
            self.team_name
        )

        self.add_item(
            self.player1
        )

        self.add_item(
            self.player2
        )

        self.add_item(
            self.player3
        )

        self.add_item(
            self.player4
        )

    async def on_submit(
        self,
        interaction
    ):

        team = self.project["teams"][
            self.index
        ]

        team["team_name"] = (
            self.team_name.value
        )

        team["player1"] = (
            self.player1.value
        )

        team["player2"] = (
            self.player2.value
        )

        team["player3"] = (
            self.player3.value
        )

        team["player4"] = (
            self.player4.value
        )

        self.save_callback(
            self.project
        )

        await interaction.response.send_message(
            "✅ 팀 정보를 수정했어!",
            ephemeral=True
        )


class RosterView(
    discord.ui.View
):

    def __init__(
        self,
        project,
        save_callback
    ):

        super().__init__(
            timeout=300
        )

        options = []

        for i, team in enumerate(
            project["teams"][:25]
        ):

            roster = team.get(
                "roster_size",
                4
            )

            options.append(
                discord.SelectOption(
                    label=(
                        f"{i + 1}. "
                        f"{team['team_name']} "
                        f"({roster}인)"
                    ),
                    value=str(i)
                )
            )

        if options:

            self.add_item(
                RosterSelect(
                    project,
                    save_callback,
                    options
                )
            )


class RosterSelect(
    discord.ui.Select
):

    def __init__(
        self,
        project,
        save_callback,
        options
    ):

        super().__init__(
            placeholder="팀 선택",
            options=options
        )

        self.project = project
        self.save_callback = save_callback

    async def callback(
        self,
        interaction
    ):

        index = int(
            self.values[0]
        )

        team = self.project["teams"][index]

        current = team.get(
            "roster_size",
            4
        )

        new_size = (
            3 if current == 4
            else 4
        )

        team["roster_size"] = new_size

        if new_size == 3:

            team["player4"] = ""

        self.save_callback(
            self.project
        )

        await interaction.response.send_message(
            f"✅ `{team['team_name']}` → "
            f"**{new_size}인 로스터**로 변경했어!",
            ephemeral=True
        )


class AddTeamModal(
    discord.ui.Modal
):

    def __init__(
        self,
        project,
        save_callback
    ):

        super().__init__(
            title="팀 추가"
        )

        self.project = project
        self.save_callback = save_callback

        self.team_name = discord.ui.TextInput(
            label="팀명",
            required=True
        )

        self.player1 = discord.ui.TextInput(
            label="선수 1",
            required=True
        )

        self.player2 = discord.ui.TextInput(
            label="선수 2",
            required=True
        )

        self.player3 = discord.ui.TextInput(
            label="선수 3",
            required=True
        )

        self.player4 = discord.ui.TextInput(
            label="선수 4",
            required=False
        )

        self.add_item(
            self.team_name
        )

        self.add_item(
            self.player1
        )

        self.add_item(
            self.player2
        )

        self.add_item(
            self.player3
        )

        self.add_item(
            self.player4
        )

    async def on_submit(
        self,
        interaction
    ):

        player4 = self.player4.value

        roster_size = (
            4 if player4 else 3
        )

        self.project["teams"].append({
            "team_name": self.team_name.value,
            "roster_size": roster_size,
            "player1": self.player1.value,
            "player2": self.player2.value,
            "player3": self.player3.value,
            "player4": player4,
            "description": ""
        })

        self.save_callback(
            self.project
        )

        await interaction.response.send_message(
            f"✅ {roster_size}인 팀을 추가했어!",
            ephemeral=True
        )


class DeleteTeamView(
    discord.ui.View
):

    def __init__(
        self,
        project,
        save_callback
    ):

        super().__init__(
            timeout=300
        )

        options = []

        for i, team in enumerate(
            project["teams"][:25]
        ):

            options.append(
                discord.SelectOption(
                    label=(
                        f"{i + 1}. "
                        f"{team['team_name']}"
                    ),
                    value=str(i)
                )
            )

        if options:

            self.add_item(
                DeleteTeamSelect(
                    project,
                    save_callback,
                    options
                )
            )


class DeleteTeamSelect(
    discord.ui.Select
):

    def __init__(
        self,
        project,
        save_callback,
        options
    ):

        super().__init__(
            placeholder="삭제할 팀 선택",
            options=options
        )

        self.project = project
        self.save_callback = save_callback

    async def callback(
        self,
        interaction
    ):

        index = int(
            self.values[0]
        )

        team_name = self.project[
            "teams"
        ][index]["team_name"]

        self.project[
            "teams"
        ].pop(index)

        self.save_callback(
            self.project
        )

        await interaction.response.send_message(
            f"🗑️ `{team_name}` 팀을 삭제했어.",
            ephemeral=True
        )
