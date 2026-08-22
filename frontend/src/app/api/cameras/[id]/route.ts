// src/app/api/cameras/[id]/route.ts
//
// DELETE kamera + SELURUH data turunannya lewat service_role, karena
// RLS anon tidak mengizinkan delete langsung dari browser.
//
// Rantai FK yang harus dihapus urut dari anak ke induk (lihat
// docs/database.md):
//
//   trafficLaneMetrics    -> trafficStates
//   trafficApproachStates -> trafficStates
//   simulationMetrics     -> simulations
//   simulations           -> trafficStates (trafficStateId)
//   trafficStates         -> cvProcessingJobs (processingJobId)
//   cctvHistory           -> cvProcessingJobs
//   cvProcessingJobs      -> cameraVideos (videoId)
//   cameraVideos          -> cameras (cameraId)
//
// Frontend sudah minta konfirmasi eksplisit ("yakin mau hapus?")
// sebelum memanggil endpoint ini, jadi di sini tidak ada lagi guard
// yang menolak penghapusan -- begitu dikonfirmasi, SEMUA data
// historis (termasuk trafficStates) ikut terhapus permanen.

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
      const { data: states, error: statesLookupError } = await supabaseAdmin
        .from("trafficStates")
        .select("id")
        .in("processingJobId", jobIds);

      if (statesLookupError) {
        return NextResponse.json(
          { error: statesLookupError.message },
          { status: 500 }
        );
      }

      const stateIds = (states ?? []).map((state) => state.id);

      if (stateIds.length > 0) {
        const { error: laneMetricsDeleteError } = await supabaseAdmin
          .from("trafficLaneMetrics")
          .delete()
          .in("trafficStateId", stateIds);

        if (laneMetricsDeleteError) {
          return NextResponse.json(
            { error: laneMetricsDeleteError.message },
            { status: 500 }
          );
        }

        const { error: approachStatesDeleteError } = await supabaseAdmin
          .from("trafficApproachStates")
          .delete()
          .in("trafficStateId", stateIds);

        if (approachStatesDeleteError) {
          return NextResponse.json(
            { error: approachStatesDeleteError.message },
            { status: 500 }
          );
        }

        const { data: simulations, error: simulationsLookupError } =
          await supabaseAdmin
            .from("simulations")
            .select("id")
            .in("trafficStateId", stateIds);

        if (simulationsLookupError) {
          return NextResponse.json(
            { error: simulationsLookupError.message },
            { status: 500 }
          );
        }

        const simulationIds = (simulations ?? []).map((sim) => sim.id);

        if (simulationIds.length > 0) {
          const { error: simulationMetricsDeleteError } = await supabaseAdmin
            .from("simulationMetrics")
            .delete()
            .in("simulationId", simulationIds);

          if (simulationMetricsDeleteError) {
            return NextResponse.json(
              { error: simulationMetricsDeleteError.message },
              { status: 500 }
            );
          }

          const { error: simulationsDeleteError } = await supabaseAdmin
            .from("simulations")
            .delete()
            .in("id", simulationIds);

          if (simulationsDeleteError) {
            return NextResponse.json(
              { error: simulationsDeleteError.message },
              { status: 500 }
            );
          }
        }

        const { error: statesDeleteError } = await supabaseAdmin
          .from("trafficStates")
          .delete()
          .in("id", stateIds);

        if (statesDeleteError) {
          return NextResponse.json(
            { error: statesDeleteError.message },
            { status: 500 }
          );
        }
      }

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
    return NextResponse.json(
      { error: cameraDeleteError.message },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}
