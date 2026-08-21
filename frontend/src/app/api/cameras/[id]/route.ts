// src/app/api/cameras/[id]/route.ts
//
// DELETE kamera + data turunannya (cameraVideos, cvProcessingJobs,
// cctvHistory) lewat service_role, karena RLS anon tidak
// mengizinkan delete langsung dari browser.

import { NextResponse } from "next/server";

import { supabaseAdmin } from "@/lib/supabaseAdmin";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const cameraId = Number(id);

  if (!Number.isFinite(cameraId)) {
    return NextResponse.json(
      { error: "ID kamera tidak valid." },
      { status: 400 }
    );
  }

  const { data: videos, error: videosLookupError } = await supabaseAdmin
    .from("cameraVideos")
    .select("id")
    .eq("cameraId", cameraId);

  if (videosLookupError) {
    return NextResponse.json(
      { error: videosLookupError.message },
      { status: 500 }
    );
  }

  const videoIds = (videos ?? []).map((video) => video.id);

  // Kode Postgres untuk foreign_key_violation -> kamera/video ini
  // masih dipakai data lain (mis. trafficStates dummy/seed) yang
  // tidak ikut dihapus di sini. Tampilkan pesan yang jelas alih-alih
  // raw SQL error ke frontend.
  const FK_VIOLATION = "23503";

  if (videoIds.length > 0) {
    const { data: jobs, error: jobsLookupError } = await supabaseAdmin
      .from("cvProcessingJobs")
      .select("id")
      .in("videoId", videoIds);

    if (jobsLookupError) {
      return NextResponse.json(
        { error: jobsLookupError.message },
        { status: 500 }
      );
    }

    const jobIds = (jobs ?? []).map((job) => job.id);

    if (jobIds.length > 0) {
      const { error: historyDeleteError } = await supabaseAdmin
        .from("cctvHistory")
        .delete()
        .in("processingJobId", jobIds);

      if (historyDeleteError) {
        return NextResponse.json(
          { error: historyDeleteError.message },
          { status: 500 }
        );
      }

      const { error: jobsDeleteError } = await supabaseAdmin
        .from("cvProcessingJobs")
        .delete()
        .in("id", jobIds);

      if (jobsDeleteError) {
        if (jobsDeleteError.code === FK_VIOLATION) {
          return NextResponse.json(
            {
              error:
                "Kamera ini tidak bisa dihapus karena masih terhubung dengan data traffic historis (trafficStates). Biasanya ini kamera/video seed awal, bukan hasil upload.",
            },
            { status: 409 }
          );
        }

        return NextResponse.json(
          { error: jobsDeleteError.message },
          { status: 500 }
        );
      }
    }

    const { error: videosDeleteError } = await supabaseAdmin
      .from("cameraVideos")
      .delete()
      .in("id", videoIds);

    if (videosDeleteError) {
      return NextResponse.json(
        { error: videosDeleteError.message },
        { status: 500 }
      );
    }
  }

  const { error: cameraDeleteError } = await supabaseAdmin
    .from("cameras")
    .delete()
    .eq("id", cameraId);

  if (cameraDeleteError) {
    if (cameraDeleteError.code === FK_VIOLATION) {
      return NextResponse.json(
        {
          error:
            "Kamera ini tidak bisa dihapus karena masih terhubung dengan data lain (video/traffic historis).",
        },
        { status: 409 }
      );
    }

    return NextResponse.json(
      { error: cameraDeleteError.message },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}
