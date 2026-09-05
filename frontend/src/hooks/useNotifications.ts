import useSWR from "swr";

export interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  severity: string;
  isRead: boolean;
  referenceId?: string;
  createdAt: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function useNotifications() {
  const { data, error, mutate } = useSWR<{ success: boolean; data: Notification[] }>(
    "http://127.0.0.1:8000/api/v1/notifications",
    fetcher,
    { refreshInterval: 5000 } // Polling setiap 5 detik (untuk header & UI notif)
  );

  const notifications = data?.data || [];
  const unreadCount = notifications.filter((n) => !n.isRead).length;

  const markAsRead = async (id: number) => {
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
