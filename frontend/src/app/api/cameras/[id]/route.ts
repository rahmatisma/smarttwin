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
import { supabase } from "@/lib/supabaseClient";
import { findOrCreateIntersection } from "../intersectionHelper";

const supabaseClient = supabaseAdmin || supabase;

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

  const { data: videos, error: videosLookupError } = await supabaseClient
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
    const { data: jobs, error: jobsLookupError } = await supabaseClient
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
      const { data: states, error: statesLookupError } = await supabaseClient
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
        const { error: laneMetricsDeleteError } = await supabaseClient
          .from("trafficLaneMetrics")
          .delete()
          .in("trafficStateId", stateIds);

        if (laneMetricsDeleteError) {
          return NextResponse.json(
            { error: laneMetricsDeleteError.message },
            { status: 500 }
          );
        }

        const { error: approachStatesDeleteError } = await supabaseClient
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
          await supabaseClient
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
          const { error: simulationMetricsDeleteError } = await supabaseClient
            .from("simulationMetrics")
            .delete()
            .in("simulationId", simulationIds);

          if (simulationMetricsDeleteError) {
            return NextResponse.json(
              { error: simulationMetricsDeleteError.message },
              { status: 500 }
            );
          }

          const { error: simulationsDeleteError } = await supabaseClient
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

        const { error: statesDeleteError } = await supabaseClient
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

      const { error: historyDeleteError } = await supabaseClient
        .from("cctvHistory")
        .delete()
        .in("processingJobId", jobIds);

      if (historyDeleteError) {
        return NextResponse.json(
          { error: historyDeleteError.message },
          { status: 500 }
        );
      }

      const { error: jobsDeleteError } = await supabaseClient
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

    const { error: videosDeleteError } = await supabaseClient
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

  const { error: cameraDeleteError } = await supabaseClient
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

export async function PATCH(
  request: Request,
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

  const body = await request.json();

  if (!body.name?.trim()) {
    return NextResponse.json(
      { error: "Nama CCTV wajib diisi." },
      { status: 400 }
    );
  }

  let intersection;
  try {
    intersection = await findOrCreateIntersection(body.intersection_name);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: "Gagal memproses persimpangan: " + message },
      { status: 500 }
    );
  }

  const { data: approach, error: approachError } = await supabaseClient
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

  const { error: updateError } = await supabaseClient
    .from("cameras")
    .update({
      name: body.name.trim(),
      intersectionId: intersection.id,
      approachId: approach.id,
    })
    .eq("id", cameraId);

  if (updateError) {
    return NextResponse.json(
      { error: updateError.message },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}
