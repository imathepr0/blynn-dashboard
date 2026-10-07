import React from "react";
import { Skeleton } from "@/components/ui/skeleton";

export default function ResumenSkeleton() {
  return (
    <div className="max-w-6xl">
      <Skeleton className="h-9 w-56 mb-6 rounded-xl" />

      {/* Row 1: Comparison cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-6">
        {[0, 1].map((i) => (
          <div key={i} className="bg-[#f5f7fa] rounded-3xl p-5 shadow-sm">
            <Skeleton className="h-4 w-28 mb-3" />
            <Skeleton className="h-8 w-32 mb-2" />
            <Skeleton className="h-3 w-36 mb-4" />
            <Skeleton className="h-20 w-full rounded-xl" />
          </div>
        ))}
      </div>

      {/* Row 2: Bar chart + side panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
        <div className="lg:col-span-2 bg-[#f5f7fa] rounded-3xl p-5 shadow-sm">
          <Skeleton className="h-5 w-40 mb-4" />
          <div className="flex items-end gap-3 h-52">
            {[60, 85, 45, 95, 70, 50, 80].map((h, i) => (
              <Skeleton key={i} className="flex-1 rounded-t-lg" style={{ height: `${h}%` }} />
            ))}
          </div>
        </div>
        <div className="space-y-5">
          <div className="bg-[#f5f7fa] rounded-3xl p-5 shadow-sm">
            <Skeleton className="h-4 w-20 mb-3" />
            <Skeleton className="h-8 w-28 mb-3" />
            <Skeleton className="h-3 w-full mb-2 rounded-full" />
            <Skeleton className="h-4 w-24" />
          </div>
          <div className="bg-[#f5f7fa] rounded-3xl p-5 shadow-sm">
            <Skeleton className="h-4 w-32 mb-3" />
            <Skeleton className="h-20 w-full rounded-xl" />
          </div>
        </div>
      </div>

      {/* Row 3: Recent expenses */}
      <div className="bg-[#f5f7fa] rounded-3xl p-5 shadow-sm">
        <Skeleton className="h-5 w-40 mb-4" />
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3">
              <Skeleton className="w-10 h-10 rounded-xl shrink-0" />
              <div className="flex-1">
                <Skeleton className="h-4 w-32 mb-2" />
                <Skeleton className="h-3 w-20" />
              </div>
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}