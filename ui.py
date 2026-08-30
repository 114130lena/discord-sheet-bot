import discord


def team_text(team, index):

    return (
        f"**{index + 1}. {team['team_name']}**\n"
        f"👤 {team['player1']} / "
        f"{team['player2']} / "
        f"{team['player3']} / "
        f"{team['player4']}\n"
        f"📝 {team['description']}\n"
    )


def project_embed(project):

    embed = discord.Embed(
        title="📋 팀 명단 분석 결과",
        description="아래 내용을 확인해주세요."
    )

    teams = project["teams"]

    if not teams:
        embed.description = "현재 등록된 팀이 없습니다."
        return embed

    text = ""

    for i, team in enumerate(teams):
        text += team_text(team, i)
        text += "\n"

    if len(text) > 4000:
        text = text[:3950] + "\n..."

    embed.description = text

    embed.set_footer(
        text=f"총 {len(teams)}팀"
    )

    return embed


class ProjectView(discord.ui.View):

    def __init__(self, project, save_callback):
        super().__init__(timeout=1800)

        self.project = project
        self.save_callback = save_callback

    @discord.ui.button(
        label="✏️ 수정",
        style=discord.ButtonStyle.primary
    )
    async def edit_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "수정 기능을 선택해주세요.",
            view=EditView(
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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        interaction: discord.Interaction,
        button: discord.ui.Button
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
        label="🔄 다시 분석",
        style=discord.ButtonStyle.secondary
    )
    async def reanalyze_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "🔄 같은 사진을 다시 분석하는 기능은 다음 단계에서 연결할게!",
            ephemeral=True
        )

    @discord.ui.button(
        label="❌ 취소",
        style=discord.ButtonStyle.secondary
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="❌ 작업이 취소되었습니다.",
            embed=None,
            view=None
        )


class EditView(discord.ui.View):

    def __init__(self, project, save_callback):
        super().__init__(timeout=300)

        self.project = project
        self.save_callback = save_callback

        options = []

        for i, team in enumerate(project["teams"][:25]):
            options.append(
                discord.SelectOption(
                    label=f"{i + 1}. {team['team_name']}",
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


class TeamSelect(discord.ui.Select):

    def __init__(self, project, save_callback, options):
        super().__init__(
            placeholder="수정할 팀 선택",
            options=options
        )

        self.project = project
        self.save_callback = save_callback

    async def callback(self, interaction):

        index = int(self.values[0])

        await interaction.response.send_modal(
            EditTeamModal(
                self.project,
                self.save_callback,
                index
            )
        )


class EditTeamModal(discord.ui.Modal):

    def __init__(self, project, save_callback, index):

        super().__init__(
            title="팀 정보 수정"
        )

        self.project = project
        self.save_callback = save_callback
        self.index = index

        team = project["teams"][index]

        self.team_name = discord.ui.TextInput(
            label="팀명",
            default=team["team_name"],
            required=True
        )

        self.player1 = discord.ui.TextInput(
            label="선수 1",
            default=team["player1"],
            required=False
        )

        self.player2 = discord.ui.TextInput(
            label="선수 2",
            default=team["player2"],
            required=False
        )

        self.player3 = discord.ui.TextInput(
            label="선수 3",
            default=team["player3"],
            required=False
        )

        self.player4 = discord.ui.TextInput(
            label="선수 4",
            default=team["player4"],
            required=False
        )

        self.add_item(self.team_name)
        self.add_item(self.player1)
        self.add_item(self.player2)
        self.add_item(self.player3)
        self.add_item(self.player4)

    async def on_submit(self, interaction):

        team = self.project["teams"][self.index]

        team["team_name"] = self.team_name.value
        team["player1"] = self.player1.value
        team["player2"] = self.player2.value
        team["player3"] = self.player3.value
        team["player4"] = self.player4.value

        self.save_callback(self.project)

        await interaction.response.send_message(
            "✅ 팀 정보를 수정했어!",
            ephemeral=True
        )


class AddTeamModal(discord.ui.Modal):

    def __init__(self, project, save_callback):

        super().__init__(
            title="팀 추가"
        )

        self.project = project
        self.save_callback = save_callback

        self.team_name = discord.ui.TextInput(
            label="팀명"
        )

        self.player1 = discord.ui.TextInput(
            label="선수 1"
        )

        self.player2 = discord.ui.TextInput(
            label="선수 2"
        )

        self.player3 = discord.ui.TextInput(
            label="선수 3"
        )

        self.player4 = discord.ui.TextInput(
            label="선수 4"
        )

        self.description = discord.ui.TextInput(
            label="한줄 설명",
            required=False,
            style=discord.TextStyle.paragraph
        )

        for item in [
            self.team_name,
            self.player1,
            self.player2,
            self.player3,
            self.player4,
            self.description
        ]:
            self.add_item(item)

    async def on_submit(self, interaction):

        self.project["teams"].append({
            "team_name": self.team_name.value,
            "player1": self.player1.value,
            "player2": self.player2.value,
            "player3": self.player3.value,
            "player4": self.player4.value,
            "description": self.description.value
        })

        self.save_callback(self.project)

        await interaction.response.send_message(
            "✅ 팀을 추가했어!",
            ephemeral=True
        )


class DeleteTeamView(discord.ui.View):

    def __init__(self, project, save_callback):

        super().__init__(timeout=300)

        options = []

        for i, team in enumerate(project["teams"][:25]):
            options.append(
                discord.SelectOption(
                    label=f"{i + 1}. {team['team_name']}",
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


class DeleteTeamSelect(discord.ui.Select):

    def __init__(self, project, save_callback, options):

        super().__init__(
            placeholder="삭제할 팀 선택",
            options=options
        )

        self.project = project
        self.save_callback = save_callback

    async def callback(self, interaction):

        index = int(self.values[0])

        team_name = self.project["teams"][index]["team_name"]

        self.project["teams"].pop(index)

        self.save_callback(self.project)

        await interaction.response.send_message(
            f"🗑️ `{team_name}` 팀을 삭제했어.",
            ephemeral=True
        )
