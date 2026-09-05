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
                    <CityIllustration />
                    <div className={styles.visualFooter}><span>DIRANCANG UNTUK KOTA INDONESIA</span><span>01 / SMART MOBILITY</span></div>
                </aside>
            </div>
        </main>
    );
}

function CityIllustration() {
    return (
        <svg className={styles.city} viewBox="0 0 600 650" fill="none" aria-hidden="true">
            <defs>
                <linearGradient id="city-water" x1="300" y1="415" x2="300" y2="650" gradientUnits="userSpaceOnUse"><stop stopColor="#70cbb7" /><stop offset="1" stopColor="#a5d5a8" /></linearGradient>
                <linearGradient id="city-tower" x1="220" y1="170" x2="310" y2="430" gradientUnits="userSpaceOnUse"><stop stopColor="#d5e794" /><stop offset="1" stopColor="#70ba8c" /></linearGradient>
                <pattern id="city-windows" width="15" height="20" patternUnits="userSpaceOnUse"><path d="M4 0V20M0 7H15" stroke="#b9edc6" strokeOpacity=".32" strokeWidth="2" /></pattern>
            </defs>
            <circle cx="455" cy="170" r="60" fill="#e4efa4" opacity=".75" />
            <path d="M0 339Q72 282 145 323T300 302T470 326T600 292V490H0Z" fill="#54a898" opacity=".45" />
            <path d="M0 363Q110 321 200 355T400 335T600 350V490H0Z" fill="#83c7a4" opacity=".55" />
            <g opacity=".6" fill="#69b8a0"><path d="M38 310H84V429H38zM105 272H140V433H105zM382 290H420V427H382zM432 312H470V432H432z" /></g>
            <path d="M150 246L211 220V432H150Z" fill="#167e79" /><path d="M211 220L239 239V432H211Z" fill="#116c6d" />
            <path d="M155 251H206V425H155Z" fill="url(#city-windows)" />
            <path d="M243 178L302 161V436H243Z" fill="url(#city-tower)" /><path d="M302 161L329 184V436H302Z" fill="#6eb68f" />
            <path d="M253 190V425M266 186V425M279 181V425M292 177V425" stroke="#e0ecae" strokeOpacity=".65" strokeWidth="3" />
            <path d="M347 218L377 435H316Z" fill="#daecb6" /><path d="M347 218L359 435H377Z" fill="#97cfac" /><path d="M346 283V425M337 345H360M330 380H365" stroke="#439c90" strokeWidth="2" />
            <path d="M74 347H133V437H74Z" fill="#b3d986" /><path d="M83 355H123V431H83Z" fill="url(#city-windows)" />
            <path d="M0 439Q140 416 280 438T600 430V650H0Z" fill="url(#city-water)" />
            <path d="M0 441H600" stroke="#d7e9a1" strokeWidth="16" />
            <path d="M0 453H600" stroke="#176f70" strokeWidth="7" />
            <g stroke="#ddf2c8" strokeOpacity=".5" strokeWidth="2"><path d="M35 486H167M203 475H291M369 487H535M130 512H257M303 528H462M20 552H124M415 566H576M195 594H350" /></g>
            <path d="M600 476C448 472 433 504 295 507S110 512 0 555V650H600Z" fill="#74b590" />
            <path d="M600 511C435 481 423 543 281 536S76 561 0 602V650H600Z" fill="#aed293" />
            <path d="M600 542C452 512 416 582 271 570S104 597 40 650H202C284 618 300 628 361 623S470 568 600 590Z" fill="#226d6a" />
            <path d="M600 566C453 538 420 604 289 599S154 616 122 650" stroke="#e9f0b1" strokeWidth="3" strokeDasharray="18 18" />
            <g fill="#155f61"><path d="M485 433V344H491V433Z" /><path d="M488 305L461 362H475L452 400H524L501 362H515Z" /><path d="M542 434V354H547V434Z" /><path d="M544 318L521 368H533L513 405H575L555 368H567Z" /></g>
            <g fill="#317f70"><path d="M40 470V407H45V470Z" /><path d="M42 366L19 420H31L11 450H73L53 420H65Z" /></g>
            <g transform="translate(390 554) rotate(-15)"><rect width="27" height="13" rx="4" fill="#eaf2bc" /><rect x="7" y="2" width="11" height="9" rx="2" fill="#4a9690" /></g>
            <g transform="translate(228 606) rotate(-8)"><rect width="24" height="12" rx="4" fill="#f6faf0" /><rect x="6" y="2" width="10" height="8" rx="2" fill="#66a39b" /></g>
            <path d="M0 650V524Q52 514 80 481Q68 530 22 550Q62 546 105 516Q82 565 28 575Q65 581 93 565Q76 612 25 608L37 650Z" fill="#155f61" />
            <path d="M572 650Q552 588 579 553Q570 599 588 615Q587 571 600 566V650Z" fill="#256f64" />
        </svg>
    );
}
