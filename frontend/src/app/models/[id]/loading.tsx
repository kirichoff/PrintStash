import { Skeleton } from "@/components/ui/skeleton";

export default function ModelDetailLoading() {
  return (
    <div className="flex h-full">
      <div className="flex-1 p-6 flex flex-col gap-6">
        <div className="flex items-center gap-4">
          <Skeleton className="w-96 h-96 rounded" />
          <div className="flex flex-col gap-3 flex-1">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-96" />
            <Skeleton className="h-4 w-80" />
            <div className="flex gap-2 mt-2">
              <Skeleton className="h-6 w-20 rounded" />
              <Skeleton className="h-6 w-16 rounded" />
            </div>
          </div>
        </div>
        <div className="flex gap-4">
          <div className="flex-1">
            <Skeleton className="h-5 w-32 mb-3" />
            <Skeleton className="h-20 w-full rounded" />
          </div>
          <div className="w-64 space-y-2">
            <Skeleton className="h-5 w-20 mb-3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </div>
      </div>
    </div>
  );
}
