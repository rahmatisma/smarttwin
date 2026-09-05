import useSWR from "swr";

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  severity: string;
  isRead: boolean;
  referenceId?: string;
  createdAt: string;
}

type NotificationPayload = Notification & {
  is_read?: boolean;
  reference_id?: string;
  created_at?: string;
};

const fetcher = async (url: string) => {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Gagal mengambil notifikasi (${response.status})`);

  const payload = (await response.json()) as {
    success: boolean;
    data: NotificationPayload[];
  };

  return {
    ...payload,
    data: payload.data.map((notification) => ({
      ...notification,
      isRead: notification.isRead ?? notification.is_read ?? false,
      referenceId: notification.referenceId ?? notification.reference_id,
      createdAt: notification.createdAt ?? notification.created_at ?? "",
    })),
  };
};

export function useNotifications() {
  const { data, error, mutate } = useSWR<{ success: boolean; data: Notification[] }>(
    "http://127.0.0.1:8000/api/v1/notifications",
    fetcher,
    { refreshInterval: 5000 } // Polling setiap 5 detik (untuk header & UI notif)
  );

  const notifications = data?.data || [];
  const unreadCount = notifications.filter((n) => !n.isRead).length;

  const markAsRead = async (id: string) => {
    try {
      await fetch(`http://127.0.0.1:8000/api/v1/notifications/${id}/read`, {
        method: "PATCH",
      });
      // Optimistic update
      mutate(
        {
          success: true,
          data: notifications.map((n) =>
            n.id === id ? { ...n, isRead: true } : n
          ),
        },
        false
      );
    } catch (err) {
      console.error("Gagal menandai notifikasi dibaca", err);
    }
  };

  return {
    notifications,
    unreadCount,
    isLoading: !error && !data,
    isError: error,
    markAsRead,
    mutate,
  };
}
