from app.services.supabase_client import get_supabase

class NotificationService:
    def get_notifications(self, limit: int = 50):
        supabase = get_supabase()
        res = (
            supabase.table("notifications")
            .select("*")
            .order("createdAt", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def mark_as_read(self, notification_id: int):
        supabase = get_supabase()
        res = (
            supabase.table("notifications")
            .update({"isRead": True})
            .eq("id", notification_id)
            .execute()
        )
        return res.data

    def create_notification(self, type: str, title: str, message: str, severity: str, reference_id: str = None):
        supabase = get_supabase()
        
        # Deduplication check
        if reference_id:
            existing = (
                supabase.table("notifications")
                .select("id")
                .eq("referenceId", reference_id)
                .eq("type", type)
                .limit(1)
                .execute()
            )
            if existing.data:
                return existing.data[0]
                
        payload = {
            "type": type,
            "title": title,
            "message": message,
            "severity": severity,
            "isRead": False,
        }
        if reference_id:
            payload["referenceId"] = reference_id
            
        res = supabase.table("notifications").insert(payload).execute()
        return res.data[0] if res.data else None

notification_service = NotificationService()
