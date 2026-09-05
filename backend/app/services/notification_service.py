from app.services.supabase_client import get_supabase

class NotificationService:
    def get_notifications(self, limit: int = 50):
        supabase = get_supabase()
        res = (
            supabase.table("notifications")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def mark_as_read(self, notification_id: str):
        supabase = get_supabase()
        res = (
            supabase.table("notifications")
            .update({"is_read": True})
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
                .eq("reference_id", reference_id)
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
            "is_read": False,
        }
        if reference_id:
            payload["reference_id"] = reference_id
            
        res = supabase.table("notifications").insert(payload).execute()
        return res.data[0] if res.data else None

notification_service = NotificationService()
