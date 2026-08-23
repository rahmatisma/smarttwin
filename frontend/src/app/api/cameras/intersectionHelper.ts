import { supabaseAdmin } from "@/lib/supabaseAdmin";
import { supabase } from "@/lib/supabaseClient";

const supabaseClient = supabaseAdmin || supabase;

export async function findOrCreateIntersection(name: string) {
  const trimmedName = name.trim();
  const slug = trimmedName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

  // Find existing by name (case-insensitive) or by intersectionId
  const { data: existing, error: existingError } = await supabaseClient
    .from("intersections")
    .select("id")
    .ilike("name", trimmedName)
    .maybeSingle();

  if (existing) {
    return existing;
  }

  // Not found, create new
  const { data: newIntersection, error: insertError } = await supabaseClient
    .from("intersections")
    .insert({
      intersectionId: slug,
      name: trimmedName,
      status: "active",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    })
    .select("id")
    .single();

  if (insertError || !newIntersection) {
    throw new Error(insertError?.message ?? "Failed to create intersection");
  }

  // Insert approaches
  const approaches = ["north", "south", "east", "west"].map(approach => ({
    intersectionId: newIntersection.id,
    approach: approach,
    createdAt: new Date().toISOString()
  }));

  const { error: approachesError } = await supabaseClient
    .from("approaches")
    .insert(approaches);

  if (approachesError) {
    throw new Error(approachesError.message);
  }

  return newIntersection;
}
