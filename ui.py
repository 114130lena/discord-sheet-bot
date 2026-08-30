import discord

SHEET_URL = "https://docs.google.com/spreadsheets/d/1FARr4g1gNM1P9oaFvpFSd3xWJo1BtgBy9398WwlzU8M/edit?usp=sharing"


def project_embed(project):
    teams = project.get("teams", [])
    embed = discord.Embed(title="📊 전력분석 결과", description=f"총 **{len(teams)}팀**\nAI 추출 결과를 확인하고 수정한 뒤 저장하세요.")
    for index, team in enumerate(teams, 1):
        name = team.get("team_name", ""); tag = team.get("team_tag", "")
        title = f"{name} [{tag}]" if name and tag else (name or tag or f"팀 {index}")
        try: roster_size = int(team.get("roster_size", 4))
        except Exception: roster_size = 4
        players = [team.get(f"player{i}", "") for i in range(1, 5)]
        players = players[:3] if roster_size == 3 else players
        text = "\n".join(f"{i}. {p or '-'}" for i, p in enumerate(players, 1)) or "-"
        note = team.get("notes", "")
        if note: text += f"\n📝 {note}"
        embed.add_field(name=f"{index}. {title}", value=text, inline=True)
    suggestions = project.get("db_suggestions", {})
    parts = []
    if suggestions.get("teams"): parts.append(f"🆕 신규 팀 {len(suggestions['teams'])}개")
    if suggestions.get("players"): parts.append(f"🆕 신규 선수 {len(suggestions['players'])}명")
    if suggestions.get("transfers"): parts.append(f"🔄 이적 의심 {len(suggestions['transfers'])}건")
    if parts: embed.set_footer(text=" / ".join(parts) + " · DB 반영 버튼을 누르기 전까지 DB는 변경되지 않습니다.")
    return embed


class TeamEditModal(discord.ui.Modal):
    def __init__(self, project, index, parent_view):
        super().__init__(title="팀 정보 수정"); self.project=project; self.index=index; self.parent_view=parent_view
        team=project["teams"][index]
        self.team_name=discord.ui.TextInput(label="팀명", default=team.get("team_name",""), required=False, max_length=100)
        self.team_tag=discord.ui.TextInput(label="약칭", default=team.get("team_tag",""), required=False, max_length=30)
        self.roster=discord.ui.TextInput(label="로스터 인원 (3 또는 4)", default=str(team.get("roster_size",4)), required=True, max_length=1)
        players="\n".join(team.get(f"player{i}","") for i in range(1,5) if team.get(f"player{i}",""))
        self.players=discord.ui.TextInput(label="선수 (한 줄에 한 명)", default=players, required=False, max_length=300, style=discord.TextStyle.paragraph)
        self.notes=discord.ui.TextInput(label="팀 메모", default=team.get("notes",""), required=False, max_length=500, style=discord.TextStyle.paragraph)
        for item in (self.team_name,self.team_tag,self.roster,self.players,self.notes): self.add_item(item)
    async def on_submit(self, interaction):
        roster=self.roster.value.strip()
        if roster not in {"3","4"}: await interaction.response.send_message("❌ 로스터 인원은 3 또는 4만 입력할 수 있습니다.",ephemeral=True); return
        team=self.project["teams"][self.index]; names=[x.strip() for x in self.players.value.splitlines() if x.strip()][:4]
        team["team_name"]=self.team_name.value.strip(); team["team_tag"]=self.team_tag.value.strip(); team["roster_size"]=int(roster)
        for i in range(1,5): team[f"player{i}"]=names[i-1] if i<=len(names) and i<=int(roster) else ""
        team["notes"]=self.notes.value.strip()
        await interaction.response.edit_message(content="📊 **전력분석 결과**",embed=project_embed(self.project),view=self.parent_view)


class AddTeamModal(discord.ui.Modal):
    def __init__(self, project, parent_view):
        super().__init__(title="팀 추가"); self.project=project; self.parent_view=parent_view
        self.team_name=discord.ui.TextInput(label="팀명",required=False,max_length=100); self.team_tag=discord.ui.TextInput(label="약칭",required=False,max_length=30)
        self.roster=discord.ui.TextInput(label="로스터 인원 (3 또는 4)",default="4",required=True,max_length=1)
        self.players=discord.ui.TextInput(label="선수 (한 줄에 한 명)",required=False,max_length=300,style=discord.TextStyle.paragraph)
        self.notes=discord.ui.TextInput(label="팀 메모",required=False,max_length=500,style=discord.TextStyle.paragraph)
        for item in (self.team_name,self.team_tag,self.roster,self.players,self.notes): self.add_item(item)
    async def on_submit(self, interaction):
        roster=self.roster.value.strip()
        if roster not in {"3","4"}: await interaction.response.send_message("❌ 로스터 인원은 3 또는 4만 입력할 수 있습니다.",ephemeral=True); return
        names=[x.strip() for x in self.players.value.splitlines() if x.strip()][:4]
        team={"team_name":self.team_name.value.strip(),"team_tag":self.team_tag.value.strip(),"roster_size":int(roster),"player1":names[0] if len(names)>0 else "","player2":names[1] if len(names)>1 else "","player3":names[2] if len(names)>2 else "","player4":names[3] if len(names)>3 and int(roster)>=4 else "","experiment1":"","experiment2":"","experiment3":"","experiment4":"","strategy":"","combat_points":"","notes":self.notes.value.strip()}
        self.project.setdefault("teams",[]).append(team)
        await interaction.response.edit_message(content="📊 **전력분석 결과**",embed=project_embed(self.project),view=self.parent_view)


class TeamSelect(discord.ui.Select):
    def __init__(self,project,parent_view):
        self.project=project; self.parent_view=parent_view; options=[]
        for i,team in enumerate(project.get("teams",[])):
            label=team.get("team_name") or team.get("team_tag") or f"팀 {i+1}"; options.append(discord.SelectOption(label=label[:100],value=str(i)))
        if not options: options=[discord.SelectOption(label="팀 없음",value="-1")]
        super().__init__(placeholder="수정할 팀 선택",options=options)
    async def callback(self,interaction):
        index=int(self.values[0])
        if index<0: await interaction.response.send_message("❌ 수정할 팀이 없습니다.",ephemeral=True); return
        await interaction.response.send_modal(TeamEditModal(self.project,index,self.parent_view))


class DeleteTeamSelect(discord.ui.Select):
    def __init__(self,project,parent_view):
        self.project=project; self.parent_view=parent_view; options=[]
        for i,team in enumerate(project.get("teams",[])):
            label=team.get("team_name") or team.get("team_tag") or f"팀 {i+1}"; options.append(discord.SelectOption(label=label[:100],value=str(i)))
        if not options: options=[discord.SelectOption(label="팀 없음",value="-1")]
        super().__init__(placeholder="삭제할 팀 선택",options=options)
    async def callback(self,interaction):
        index=int(self.values[0])
        if index<0: await interaction.response.send_message("❌ 삭제할 팀이 없습니다.",ephemeral=True); return
        self.project["teams"].pop(index); await interaction.response.edit_message(content="📊 **전력분석 결과**",embed=project_embed(self.project),view=self.parent_view)


class EditView(discord.ui.View):
    def __init__(self,project,parent_view):
        super().__init__(timeout=180); self.project=project; self.parent_view=parent_view; self.add_item(TeamSelect(project,parent_view))
    @discord.ui.button(label="➕ 팀 추가",style=discord.ButtonStyle.success)
    async def add_team(self,interaction,button): await interaction.response.send_modal(AddTeamModal(self.project,self.parent_view))
    @discord.ui.button(label="🗑️ 팀 삭제",style=discord.ButtonStyle.danger)
    async def delete_team(self,interaction,button): await interaction.response.edit_message(content="🗑️ **삭제할 팀을 선택하세요.**",embed=project_embed(self.project),view=DeleteTeamView(self.project,self.parent_view))
    @discord.ui.button(label="↩️ 돌아가기",style=discord.ButtonStyle.secondary)
    async def back(self,interaction,button): await interaction.response.edit_message(content="📊 **전력분석 결과**",embed=project_embed(self.project),view=self.parent_view)


class DeleteTeamView(discord.ui.View):
    def __init__(self,project,parent_view): super().__init__(timeout=180); self.project=project; self.parent_view=parent_view; self.add_item(DeleteTeamSelect(project,parent_view))
    @discord.ui.button(label="↩️ 돌아가기",style=discord.ButtonStyle.secondary)
    async def back(self,interaction,button): await interaction.response.edit_message(content="📊 **전력분석 결과**",embed=project_embed(self.project),view=self.parent_view)


class ProjectView(discord.ui.View):
    def __init__(self,project,save_callback=None,db_callback=None):
        super().__init__(timeout=300); self.project=project; self.save_callback=save_callback; self.db_callback=db_callback
        self.add_item(discord.ui.Button(label="📊 Google Sheets 열기", style=discord.ButtonStyle.link, url=SHEET_URL))
    @discord.ui.button(label="✏️ 수정",style=discord.ButtonStyle.primary)
    async def edit_button(self,interaction,button): await interaction.response.edit_message(content="✏️ **수정할 팀을 선택하세요.**",embed=project_embed(self.project),view=EditView(self.project,self))
    @discord.ui.button(label="🧠 DB 반영",style=discord.ButtonStyle.secondary)
    async def db_button(self,interaction,button):
        if self.db_callback is None: await interaction.response.send_message("❌ DB 기능이 연결되지 않았습니다.",ephemeral=True); return
        await interaction.response.defer()
        try:
            result=self.db_callback(self.project)
            if hasattr(result,"__await__"): result=await result
            for child in self.children:
                if getattr(child,"label","")=="🧠 DB 반영": child.disabled=True
            await interaction.edit_original_response(content=f"🧠 **DB 반영 완료.**\n신규 팀 {result.get('teams',0)}개 · 신규 선수 {result.get('players',0)}명 · 이적 {result.get('transfers',0)}건\n💾 반영 전 DB 백업도 생성했습니다.",embed=project_embed(self.project),view=self)
        except Exception as e:
            print(f"DB 반영 오류: {e}"); await interaction.edit_original_response(content=f"❌ **DB 반영 실패:** `{type(e).__name__}: {e}`",embed=project_embed(self.project),view=self)
    @discord.ui.button(label="💾 시트에 저장",style=discord.ButtonStyle.success)
    async def save_button(self,interaction,button):
        if self.save_callback is None: await interaction.response.send_message("❌ 저장 기능이 연결되지 않았습니다.",ephemeral=True); return
        await interaction.response.defer()
        try:
            result=self.save_callback(self.project)
            url = await result if hasattr(result,"__await__") else result
            await interaction.edit_original_response(content="✅ **Google Sheets 저장 완료.**\n아래 버튼으로 시트를 열 수 있습니다.",embed=project_embed(self.project),view=self)
        except Exception as e:
            print(f"Google Sheets 저장 오류: {e}"); await interaction.edit_original_response(content=f"❌ **저장 실패:** `{type(e).__name__}`",embed=project_embed(self.project),view=self
    @discord.ui.button(label="❌ 닫기",style=discord.ButtonStyle.danger)
    async def close_button(self,interaction,button):
        try:
            await interaction.response.defer()
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            try:
                await interaction.response.edit_message(content="🛑 **전력분석 결과를 닫았습니다.**",view=None)
            except Exception:
                pass
        except Exception as e:
            print(f"결과 메시지 삭제 오류: {e}")
