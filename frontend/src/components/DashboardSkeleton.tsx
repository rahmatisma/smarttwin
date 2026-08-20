"use client";

export default function DashboardSkeleton() {
    return (
        <div className="animate-pulse space-y-5 p-5 md:p-7">

            {/* =====================================================
          TOP SUMMARY CARDS
      ===================================================== */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">

                {[1, 2, 3, 4].map((item) => (
                    <div
                        key={item}
                        className="rounded-xl border border-border bg-surface p-5"
                    >
                        <div className="h-3 w-24 rounded bg-surface-2" />

                        <div className="mt-4 h-7 w-20 rounded bg-surface-2" />

                        <div className="mt-3 h-2.5 w-32 rounded bg-surface-2" />
                    </div>
                ))}

            </div>

            {/* =====================================================
          MAIN CONTENT
      ===================================================== */}
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">

                {/* TRAFFIC CARD */}
                <div className="rounded-xl border border-border bg-surface p-5 xl:col-span-2">

                    <div className="flex items-center justify-between">
                        <div>
                            <div className="h-4 w-32 rounded bg-surface-2" />
                            <div className="mt-2 h-2.5 w-48 rounded bg-surface-2" />
                        </div>

                        <div className="h-8 w-24 rounded-lg bg-surface-2" />
                    </div>

                    {/* GRAPH */}
                    <div className="mt-6 flex h-64 items-end gap-3">

                        {[45, 65, 35, 80, 55, 70, 40, 85, 60, 75, 50, 65].map(
                            (height, index) => (
                                <div
                                    key={index}
                                    className="flex-1 rounded-t bg-surface-2"
                                    style={{
                                        height: `${height}%`,
                                    }}
                                />
                            )
                        )}

                    </div>

                </div>

                {/* CAMERA FEED */}
                <div className="rounded-xl border border-border bg-surface p-5">

                    <div className="h-4 w-28 rounded bg-surface-2" />

                    <div className="mt-4 aspect-video rounded-lg bg-surface-2" />

                    <div className="mt-4 space-y-3">

                        <div className="flex justify-between">
                            <div className="h-3 w-20 rounded bg-surface-2" />
                            <div className="h-3 w-10 rounded bg-surface-2" />
                        </div>

                        <div className="flex justify-between">
                            <div className="h-3 w-16 rounded bg-surface-2" />
                            <div className="h-3 w-10 rounded bg-surface-2" />
                        </div>

                        <div className="flex justify-between">
                            <div className="h-3 w-24 rounded bg-surface-2" />
                            <div className="h-3 w-10 rounded bg-surface-2" />
                        </div>

                    </div>

                </div>

            </div>

            {/* =====================================================
          LOWER CARDS
      ===================================================== */}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">

                {/* CARD 1 */}
                <div className="rounded-xl border border-border bg-surface p-5">

                    <div className="h-4 w-36 rounded bg-surface-2" />

                    <div className="mt-5 space-y-4">

                        {[1, 2, 3, 4].map((item) => (
                            <div
                                key={item}
                                className="flex items-center gap-3"
                            >
                                <div className="h-9 w-9 rounded-lg bg-surface-2" />

                                <div className="flex-1">
                                    <div className="h-3 w-32 rounded bg-surface-2" />
                                    <div className="mt-2 h-2.5 w-20 rounded bg-surface-2" />
                                </div>

                                <div className="h-3 w-12 rounded bg-surface-2" />
                            </div>
                        ))}

                    </div>

                </div>

                {/* CARD 2 */}
                <div className="rounded-xl border border-border bg-surface p-5">

                    <div className="h-4 w-40 rounded bg-surface-2" />

                    <div className="mt-5 space-y-4">

                        {[1, 2, 3, 4].map((item) => (
                            <div
                                key={item}
                                className="flex items-center justify-between"
                            >
                                <div>
                                    <div className="h-3 w-28 rounded bg-surface-2" />
                                    <div className="mt-2 h-2.5 w-20 rounded bg-surface-2" />
                                </div>

                                <div className="h-7 w-16 rounded bg-surface-2" />
                            </div>
                        ))}

                    </div>

                </div>

            </div>

        </div>
    );
}