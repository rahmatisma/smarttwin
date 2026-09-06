"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, LoaderCircle, Lock, Mail } from "lucide-react";
import Image from "next/image";
import styles from "./login.module.css";

import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
    const router = useRouter();

    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function handleSubmit(
        event: React.FormEvent<HTMLFormElement>
    ) {
        event.preventDefault();

        setLoading(true);
        setError(null);

        const { error: signInError } =
            await supabase.auth.signInWithPassword({
                email,
                password,
            });

        setLoading(false);

        if (signInError) {
            setError(
                signInError.message === "Invalid login credentials"
                    ? "Email atau password salah."
                    : signInError.message
            );
            return;
        }

        router.replace("/dashboard");
        router.refresh();
    }

    return (
        <main className={styles.page}>
            <div className={styles.layout}>
                <section className={styles.formSide} aria-labelledby="login-title">
                    <div className={styles.brand}>
                        <Image src="/logo-light.png" alt="SmartTwin" width={82} height={82} />
                        <span>TRAFFIC MANAGEMENT SYSTEM</span>
                    </div>

                    <div className={styles.formContent}>
                        <p className={styles.eyebrow}>SELAMAT DATANG KEMBALI</p>
                        <h1 id="login-title">Langkah kecil untuk<br />kota yang lebih baik<span>.</span></h1>
                        <p className={styles.description}>Masuk ke SmartTwin dan mulai pantau lalu lintas Anda.</p>

                        <form onSubmit={handleSubmit} className={styles.form} aria-busy={loading}>
                            <div className={styles.field}>
                                <label htmlFor="login-email">Email</label>
                                <div className={styles.inputWrap}>
                                    <Mail size={18} aria-hidden="true" />
                                    <input id="login-email" name="email" type="email" autoComplete="email"
                                        value={email} onChange={(event) => setEmail(event.target.value)}
                                        placeholder="nama@email.com" required aria-invalid={!!error}
                                        aria-describedby={error ? "login-error" : undefined} />
                                </div>
                            </div>

                            <div className={styles.field}>
                                <label htmlFor="login-password">Kata sandi</label>
                                <div className={styles.inputWrap}>
                                    <Lock size={18} aria-hidden="true" />
                                    <input id="login-password" name="password" type="password" autoComplete="current-password"
                                        value={password} onChange={(event) => setPassword(event.target.value)}
                                        placeholder="Masukkan kata sandi" required aria-invalid={!!error}
                                        aria-describedby={error ? "login-error" : undefined} />
                                </div>
                            </div>

                            {error && <p id="login-error" role="alert" className={styles.error}>{error}</p>}

                            <button type="submit" disabled={loading} className={styles.submit}>
                                {loading ? "Sedang masuk..." : "Masuk ke dashboard"}
                                {loading ? <LoaderCircle size={18} className={styles.spinner} aria-hidden="true" /> : <ArrowRight size={18} aria-hidden="true" />}
                            </button>
                        </form>

                        <p className={styles.register}>Belum punya akun? <Link href="/register">Buat akun baru <ArrowRight size={13} aria-hidden="true" /></Link></p>
                    </div>

                    <footer className={styles.footer}><span className={styles.footerDot} /> SmartTwin &middot; Mobilitas cerdas, kota selaras.</footer>
                </section>

                <aside className={styles.visualSide} aria-label="SmartTwin untuk mobilitas perkotaan">
                    <div className={styles.visualCopy}>
                        <span className={styles.visualEyebrow}>SMARTER TRAFFIC. BETTER CITIES.</span>
                        <h2>Perjalanan lebih lancar.<br /><span>Kota lebih terhubung.</span></h2>
                        <p>Memahami setiap pergerakan.<br />Membuka jalan untuk perubahan.</p>
                    </div>
                    <div className={styles.artwork}><CityIllustration /></div>
                    <div className={styles.visualFooter}><span>DIRANCANG UNTUK KOTA INDONESIA</span><span>01 / SMART MOBILITY</span></div>
                </aside>
            </div>
        </main>
    );
}

function CityIllustration() {
    return (
        <svg className={styles.city} viewBox="0 0 600 500" preserveAspectRatio="xMidYMid meet" fill="none" aria-hidden="true">
            <defs>
                <linearGradient id="city-blue" x1="180" y1="110" x2="300" y2="360" gradientUnits="userSpaceOnUse"><stop stopColor="#38bdf8" /><stop offset="1" stopColor="#1469a7" /></linearGradient>
                <linearGradient id="city-gold" x1="350" y1="110" x2="400" y2="340" gradientUnits="userSpaceOnUse"><stop stopColor="#ffce7b" /><stop offset="1" stopColor="#f59a28" /></linearGradient>
                <linearGradient id="city-base" x1="300" y1="290" x2="300" y2="450" gradientUnits="userSpaceOnUse"><stop stopColor="#295c88" /><stop offset="1" stopColor="#173c60" /></linearGradient>
            </defs>
            <circle cx="302" cy="228" r="183" fill="#38bdf8" opacity=".035" />
            <circle cx="302" cy="228" r="183" stroke="#76caff" strokeOpacity=".14" strokeDasharray="4 10" />
            <circle cx="450" cy="103" r="37" fill="#ffd18a" />
            <circle cx="450" cy="103" r="48" stroke="#ffd18a" strokeOpacity=".13" />
            <ellipse cx="300" cy="432" rx="228" ry="25" fill="#061a30" opacity=".35" />
            <path d="M58 340Q300 253 542 340V367Q300 485 58 367Z" fill="#102f4e" />
            <path d="M58 340Q300 231 542 340Q300 458 58 340Z" fill="url(#city-base)" stroke="#6ab5e4" strokeOpacity=".35" />
            <path d="M87 347Q300 258 513 347" stroke="#5d9bc7" strokeOpacity=".3" strokeWidth="2" />
            <path d="M116 363Q214 324 296 352T475 366" stroke="#0b263f" strokeWidth="34" strokeLinecap="round" />
            <path d="M116 363Q214 324 296 352T475 366" stroke="#d2e9fa" strokeWidth="2" strokeDasharray="10 12" strokeLinecap="round" />
            <path d="M129 309V218L178 204V315Z" fill="#398aca" />
            <path d="M178 204L202 219V327L178 315Z" fill="#1c5c95" />
            <path d="M139 233L164 226M139 250L164 243M139 267L164 260M139 284L164 277" stroke="#a9e4ff" strokeWidth="4" strokeOpacity=".6" />
            <path d="M208 316V126L270 103V316Z" fill="url(#city-blue)" />
            <path d="M270 103L299 125V332L270 316Z" fill="#105b99" />
            <path d="M208 126L237 147L299 125L270 103Z" fill="#69cbfa" />
            <path d="M221 153V299M239 149V299M257 143V299" stroke="#b8ecff" strokeWidth="4" strokeOpacity=".65" />
            <path d="M314 323V170L345 156V330Z" fill="#d4edff" />
            <path d="M345 156L364 171V341L345 330Z" fill="#76b2da" />
            <path d="M325 185V313" stroke="#fff" strokeWidth="4" />
            <path d="M368 324V130L413 150V328Z" fill="url(#city-gold)" />
            <path d="M368 130L392 115L438 136L413 150Z" fill="#ffdb99" />
            <path d="M413 150L438 136V315L413 328Z" fill="#d88227" />
            <path d="M380 153V309M394 160V313" stroke="#fff1cf" strokeWidth="4" strokeOpacity=".85" />
            <path d="M102 331V297M467 332V292M490 323V305" stroke="#81aaca" strokeWidth="4" strokeLinecap="round" />
            <path d="M102 263L84 301H120Z" fill="#458fb8" /><path d="M102 280L78 317H126Z" fill="#2d709c" />
            <path d="M467 252L446 297H488Z" fill="#6faacc" /><path d="M467 273L441 314H493Z" fill="#3d7ea6" />
            <path d="M490 283L472 315H508Z" fill="#659bbf" />
            <g transform="translate(205 341) rotate(-5)"><rect width="28" height="14" rx="5" fill="#ffca72" /><rect x="8" y="3" width="12" height="8" rx="2" fill="#22567d" /></g>
            <g transform="translate(372 369) rotate(4)"><rect width="28" height="14" rx="5" fill="#e3f4ff" /><rect x="8" y="3" width="12" height="8" rx="2" fill="#22567d" /></g>
            <circle cx="115" cy="170" r="5" fill="#38bdf8" /><circle cx="481" cy="202" r="4" fill="#ffca72" />
            <path d="M103 170H85M481 185V175" stroke="#8dd6ff" strokeOpacity=".5" strokeWidth="2" strokeLinecap="round" />
        </svg>
    );
}
