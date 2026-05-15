from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, require_role
from app.core.supabase import supabase_admin
from app.models.user import ProfileResponse, ProfileUpdate, AdminRoleUpdate

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me", response_model=ProfileResponse, summary="Get my profile")
async def get_me(current_user=Depends(get_current_user)):
    resp = (
        supabase_admin.table("profiles")
        .select("*")
        .eq("id", current_user.id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return resp.data


@router.patch("/me", response_model=ProfileResponse, summary="Update my profile")
async def update_me(update: ProfileUpdate, current_user=Depends(get_current_user)):
    data = update.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update.")
    resp = (
        supabase_admin.table("profiles")
        .update(data)
        .eq("id", current_user.id)
        .execute()
    )
    return resp.data[0]


@router.get("/verify", summary="Verify domain and auth status")
async def verify(current_user=Depends(get_current_user)):
    """Quick check — returns user email and role if token is valid."""
    resp = (
        supabase_admin.table("profiles")
        .select("role, is_verified")
        .eq("id", current_user.id)
        .single()
        .execute()
    )
    role = resp.data.get("role", "student") if resp.data else "student"
    return {
        "authenticated": True,
        "email": current_user.email,
        "user_id": current_user.id,
        "role": role,
    }


@router.post(
    "/admin/set-role",
    summary="[Admin] Change a user's role",
    dependencies=[Depends(require_role("admin"))],
)
async def admin_set_role(body: AdminRoleUpdate, current_user=Depends(get_current_user)):
    if body.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role.")
    resp = (
        supabase_admin.table("profiles")
        .update({"role": body.role.value})
        .eq("id", body.user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"success": True, "user_id": body.user_id, "new_role": body.role.value}
