import discord


# =========================================================
# Embed 생성
# =========================================================

def project_embed(project):

    teams = project.get("teams", [])

    embed = discord.Embed(
        title="📊 전력분석 결과",
        description=(
            f"총 **{len(teams)}팀**\n"
            "내용을 확인하고 필요한 부분을 수정한 뒤 저장해줘."
        )
    )

    for index, team in enumerate(teams, start=1):

        team_name = team.get(
            "team_name",
            ""
        )

        team_tag = team.get(
            "team_tag",
            ""
        )

        if team_name and team_tag:
            title = f"{team_name} [{team_tag}]"

        elif team_name:
            title = team_name

        elif team_tag:
            title = f"[{team_tag}]"

        else:
            title = "팀명 확인 필요"

        players = [
            team.get("player1", ""),
            team.get("player2", ""),
            team.get("player3", ""),
            team.get("player4", "")
        ]

        roster = "\n".join(
            f"{i + 1}. {player if player else '-'}"
            for i, player in enumerate(players)
        )

        embed.add_field(
            name=f"{index}. {title}",
            value=roster,
            inline=True
        )

    return embed


# =========================================================
# 팀 선택
# =========================================================

class TeamSelect(discord.ui.Select):

    def __init__(self, project):

        self.project = project

        teams = project.get(
            "teams",
            []
        )

        options = []

        for index, team in enumerate(teams):

            name = team.get(
                "team_name",
                ""
            )

            tag = team.get(
                "team_tag",
                ""
            )

            label = name or tag or f"팀 {index + 1}"

            if len(label) > 100:
                label = label[:100]

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(index)
                )
            )

        if not options:

            options.append(
                discord.SelectOption(
                    label="팀이 없습니다",
                    value="-1"
                )
            )

        super().__init__(
            placeholder="수정할 팀을 선택해줘",
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        index = int(
            self.values[0]
        )

        if index < 0:

            await interaction.response.send_message(
                "❌ 수정할 팀이 없어.",
                ephemeral=True
            )

            return

        team = self.project["teams"][index]

        await interaction.response.send_modal(
            TeamEditModal(
                self.project,
                index,
                team
            )
        )


# =========================================================
# 팀 수정 모달
# =========================================================

class TeamEditModal(discord.ui.Modal):

    def __init__(
        self,
        project,
        index,
        team
    ):

        super().__init__(
            title="팀 정보 수정"
        )

        self.project = project
        self.index = index

        self.team_name = discord.ui.TextInput(
            label="팀명",
            default=team.get(
                "team_name",
                ""
            ),
            required=False,
            max_length=100
        )

        self.team_tag = discord.ui.TextInput(
            label="약칭",
            default=team.get(
                "team_tag",
                ""
            ),
            required=False,
            max_length=30
        )

        self.player1 = discord.ui.TextInput(
            label="선수 1",
            default=team.get(
                "player1",
                ""
            ),
            required=False,
            max_length=50
        )

        self.player2 = discord.ui.TextInput(
            label="선수 2",
            default=team.get(
                "player2",
                ""
            ),
            required=False,
            max_length=50
        )

        self.player3 = discord.ui.TextInput(
            label="선수 3",
            default=team.get(
                "player3",
                ""
            ),
            required=False,
            max_length=50
        )

        self.add_item(self.team_name)
        self.add_item(self.team_tag)
        self.add_item(self.player1)
        self.add_item(self.player2)
        self.add_item(self.player3)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        team = self.project["teams"][self.index]

        team["team_name"] = self.team_name.value.strip()
        team["team_tag"] = self.team_tag.value.strip()

        team["player1"] = self.player1.value.strip()
        team["player2"] = self.player2.value.strip()
        team["player3"] = self.player3.value.strip()

        # 기존 4번째 선수 유지
        if "player4" not in team:
            team["player4"] = ""

        await interaction.response.edit_message(
            embed=project_embed(
                self.project
            ),
            view=ProjectView(
                self.project,
                None
            )
        )


# =========================================================
# 수정 메뉴 View
# =========================================================

class EditView(discord.ui.View):

    def __init__(self, project):

        super().__init__(
            timeout=120
        )

        self.project = project

        self.add_item(
            TeamSelect(project)
        )


# =========================================================
# 메인 View
# =========================================================

class ProjectView(discord.ui.View):

    def __init__(
        self,
        project,
        save_callback=None
    ):

        super().__init__(
            timeout=300
        )

        self.project = project
        self.save_callback = save_callback

    # =====================================================
    # 수정
    # =====================================================

    @discord.ui.button(
        label="✏️ 수정",
        style=discord.ButtonStyle.primary
    )
    async def edit_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            content="✏️ **수정할 팀을 선택해줘.**",
            embed=project_embed(
                self.project
            ),
            view=EditView(
                self.project
            )
        )

    # =====================================================
    # 저장
    # =====================================================

    @discord.ui.button(
        label="💾 시트에 저장",
        style=discord.ButtonStyle.success
    )
    async def save_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if self.save_callback is None:

            await interaction.response.send_message(
                "❌ 저장 기능이 연결되지 않았어.",
                ephemeral=True
            )

            return

        await interaction.response.defer()

        try:

            result = self.save_callback(
                self.project
            )

            # async 함수라면 기다림
            if hasattr(
                result,
                "__await__"
            ):

                await result

            await interaction.followup.send(
                "✅ **Google Sheets 저장 완료!**",
                ephemeral=True
            )

        except Exception as e:

            print(
                f"Google Sheets 저장 오류: {e}"
            )

            await interaction.followup.send(
                "❌ Google Sheets 저장 중 오류가 발생했어.",
                ephemeral=True
            )

    # =====================================================
    # 취소
    # =====================================================

    @discord.ui.button(
        label="❌ 취소",
        style=discord.ButtonStyle.danger
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await interaction.response.edit_message(
            content="🛑 **수정을 취소했어.**",
            embed=project_embed(
                self.project
            ),
            view=self
        )
