import Image from "next/image";

/**
 * Logo SmartTwin -- lockup ikon + tulisan dalam satu gambar (bukan ikon
 * polos), jadi dipasang MENGGANTIKAN kombinasi ikon+teks placeholder lama,
 * bukan disandingkan dengan teks "SmartTwin" terpisah.
 *
 * File sumber PNG berlatar transparan: logo-dark.png (tulisan putih, untuk
 * tema gelap) dan logo-light.png (tulisan navy, untuk tema terang). Keduanya
 * dirender sekaligus; yang tampil ditentukan CSS murni
 * (.brand-logo-dark/.brand-logo-light di globals.css) berdasarkan atribut
 * data-theme di <html> -- supaya tidak ada logo salah tema yang sempat
 * kelihatan sebelum JavaScript jalan.
 */
export default function Logo({
  height = 32,
  className = "",
}: {
  height?: number;
  className?: string;
}) {
  // Rasio asli file sumber persis 1:1.
  const width = height;

  return (
    <span className={`inline-flex shrink-0 items-center ${className}`}>
      <Image
        src="/logo-dark.png"
        alt="SmartTwin"
        width={width}
        height={height}
        priority
        className="brand-logo-dark"
        style={{ height, width: "auto" }}
      />
      <Image
        src="/logo-light.png"
        alt="SmartTwin"
        width={width}
        height={height}
        priority
        className="brand-logo-light"
        style={{ height, width: "auto" }}
      />
    </span>
  );
}
