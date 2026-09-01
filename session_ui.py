import discord
from ui import ProjectView as BaseProjectView, project_embed as base_project_embed
from session_manager import mark_status
from nickname_ui import NicknameTypeMixin


def project_embed(project):
    embed = base_project_embed(project)
    sid = project.get("session_id", project.get("id", "-"))
    name = project.get("session_name", "")
    event = project.get("event_name", "")
    created = str(project.get("session_created_at", "-")).replace("T", " ")
    updated = str(project.get("session_updated_at", "-")).replace("T", " ")
    status = {"active": "진행 중", "paused": "보류", "completed": "완료"}.get(project.get("session_status", "active"), "진행 중")
    meta = [f"📂 **세션:** {name or sid}", f"상태: **{status}**"]
    if event:
        meta.append(f"🏆 **대회:** {event}")
    meta.append(f"🕒 생성: `{created}` · 최근 수정: `{updated}`")
    batches = project.get("session_batches", [])
    meta.append(f"📦 분석 묶음: **{len(batches)}회**")
    embed.description = "\n".join(meta) + "\n\n" + (embed.description or "")
    return embed


class ProjectView(NicknameTypeMixin, BaseProjectView):
    """기존 분석 UI에 세션 관리와 닉네임 구분 기능을 추가합니다."""

    @discord.ui.button(label="➕ 세션 추가", style=discord.ButtonStyle.primary, row=1)
    async def session_add_hint(self, interaction, button):
        sid = self.project.get("session_id", self.project.get("id", "-"))
        await interaction.response.send_message(
            f"➕ 현재 세션 **`{sid}`**에 추가 분석을 넣으려면 `/세션추가 {sid}`를 사용해 주세요.",
            ephemeral=True,
        )

    @discord.ui.button(label="⏸️ 세션 보류", style=discord.ButtonStyle.secondary, row=1)
    async def session_pause(self, interaction, button):
        mark_status(self.project, "paused")
        await interaction.response.edit_message(
            content="⏸️ **세션을 보류 상태로 저장했습니다.** 다시 작업하려면 `/세션불러오기 세션ID`를 사용해 주세요.",
            embed=project_embed(self.project),
            view=self,
        )

    @discord.ui.button(label="✅ 세션 완료", style=discord.ButtonStyle.success, row=1)
    async def session_complete(self, interaction, button):
        mark_status(self.project, "completed")
        button.disabled = True
        await interaction.response.edit_message(
            content="✅ **세션을 완료 상태로 저장했습니다.** 필요하면 `/세션불러오기 세션ID`로 다시 열 수 있습니다.",
            embed=project_embed(self.project),
            view=self,
        )
