export type IntersectionSelection =
  | "all"
  | "intersection1"
  | "intersection2"
  | "intersection3"
  | "intersection4";

export interface IntersectionConfig {
    id: Exclude<IntersectionSelection, "all">;
    name: string;
    databaseId: string;
    cameraName: string;
}

export const ALL_INTERSECTIONS: IntersectionConfig[] = [
    {
        id: "intersection1",
        name: "Simpang Surabaya",
        databaseId: "simpang1",
        cameraName: "CCTV 1",
    },
    {
        id: "intersection2",
        name: "Simpang Kandang",
        databaseId: "simpang2",
        cameraName: "CCTV 2 (Jl Magelang)",
    },
    {
        id: "intersection3",
        name: "Simpang 3",
        databaseId: "simpang3",
        cameraName: "CCTV 3 (Jl Kyai Mojo)",
    },
    {
        id: "intersection4",
        name: "Simpang Pingit",
        databaseId: "simpang4-pingit",
        cameraName: "CCTV 4 (Jl Pangeran Diponegoro)",
    },
];

export const INTERSECTION_OPTIONS: Array<{
    id: IntersectionSelection;
    name: string;
}> = [
    { id: "all", name: "Semua Simpang" },
    ...ALL_INTERSECTIONS.map(({ id, name }) => ({ id, name })),
];

export function getIntersectionName(selection: IntersectionSelection): string {
    if (selection === "all") {
        return "Semua Simpang";
    }

    return (
        ALL_INTERSECTIONS.find((intersection) => intersection.id === selection)
            ?.name ?? "Semua Simpang"
    );
}

export function getIntersectionDatabaseIds(
    selection: IntersectionSelection
): string[] {
    if (selection === "all") {
        return ALL_INTERSECTIONS.map(({ databaseId }) => databaseId);
    }

    const intersection = ALL_INTERSECTIONS.find(
        ({ id }) => id === selection
    );

    return intersection ? [intersection.databaseId] : [];
}
