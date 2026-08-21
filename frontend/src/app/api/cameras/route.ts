// src/app/api/cameras/route.ts
//
// Route Handler server-side untuk kamera CCTV dengan sumber
// URL/RTSP (metadata saja, tidak ada file untuk disimpan).
//
// Untuk upload video sungguhan, lihat
// backend/app/api/routes/cctv.py (POST /api/v1/cctv/upload) —
// itu yang mengurus penyimpanan file ke Hugging Face Hub.
//
// Menggunakan supabaseAdmin (service_role) karena RLS di
// tabel cameras hanya mengizinkan SELECT untuk anon —
// insert/delete harus lewat sini, bukan langsung dari browser.

import { NextResponse } from "next/server";

import { supabaseAdmin } from "@/lib/supabaseAdmin";
import { DEFAULT_INTERSECTION_ID } from "@/lib/supabaseData";

interface CreateCameraBody {
  name: string;
  approach: "north" | "south" | "east" | "west";
  sourceType: "url" | "rtsp";
  source: string;
}

export async function POST(request: Request) {
  const body: CreateCameraBody = await request.json();

  if (!body.name?.trim()) {
    return NextResponse.json(
      { error: "Nama CCTV wajib diisi." },
      { status: 400 }
    );
  }

  if (!body.approach) {
    return NextResponse.json(
      { error: "Arah kamera wajib diisi." },
      { status: 400 }
    );
  }

  if (!body.source?.trim()) {
    return NextResponse.json(
      { error: "URL CCTV wajib diisi." },
      { status: 400 }
    );
  }

  const { data: intersection, error: intersectionError } =
    await supabaseAdmin
      .from("intersections")
      .select("id")
      .eq("intersectionId", DEFAULT_INTERSECTION_ID)
      .maybeSingle();

  if (intersectionError || !intersection) {
    return NextResponse.json(
      { error: "Intersection tidak ditemukan." },
      { status: 500 }
    );
  }

  const { data: approach, error: approachError } = await supabaseAdmin
    .from("approaches")
    .select("id")
    .eq("intersectionId", intersection.id)
    .eq("approach", body.approach)
    .maybeSingle();

  if (approachError || !approach) {
    return NextResponse.json(
      { error: "Approach tidak ditemukan." },
      { status: 500 }
    );
  }

  const cameraId = `cam-${crypto.randomUUID()}`;

  const { data: camera, error: cameraError } = await supabaseAdmin
    .from("cameras")
    .insert({
      intersectionId: intersection.id,
      cameraId,
      name: body.name.trim(),
      approachId: approach.id,
      sourceType: "live",
      sourceUrl: body.source,
      status: body.sourceType === "rtsp" ? "waiting" : "active",
    })
    .select("id, cameraId, name, sourceType, sourceUrl, status")
    .single();

  if (cameraError || !camera) {
    return NextResponse.json(
      { error: `Gagal menyimpan kamera: ${cameraError?.message}` },
      { status: 500 }
    );
  }

  return NextResponse.json({ camera }, { status: 201 });
}
