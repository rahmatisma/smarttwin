import Link from "next/link";
import { ArrowUpRight, MapPin } from "lucide-react";

export default function DashboardWelcome({ dateLabel }: { dateLabel: string }) {
  return (
    <section className="dashboard-welcome" aria-labelledby="welcome-title">
      <div className="welcome-heading">
        <div>
          <div className="welcome-eyebrow">
            <MapPin size={13} aria-hidden="true" />
            SIMPANG PINGIT · YOGYAKARTA
          </div>
          <h1 id="welcome-title">Selamat datang di SmartTwin</h1>
          <p>Pantau lalu lintas, pahami kondisi, dan optimalkan setiap perjalanan.</p>
        </div>
        <div className="welcome-meta">
          <span>{dateLabel}</span>
          <Link href="/digitaltwin">
            Buka Digital Twin <ArrowUpRight size={15} aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}
