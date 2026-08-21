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
      await supabaseAdmin.from("cctvHistory").delete().in("processingJobId", jobIds);
      await supabaseAdmin.from("cvProcessingJobs").delete().in("id", jobIds);
    }

    await supabaseAdmin.from("cameraVideos").delete().in("id", videoIds);
  }

  const { error: cameraDeleteError } = await supabaseAdmin
    .from("cameras")
    .delete()
    .eq("id", cameraId);

  if (cameraDeleteError) {
    return NextResponse.json(
      { error: cameraDeleteError.message },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}
