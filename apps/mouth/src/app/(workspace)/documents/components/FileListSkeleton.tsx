"use client";

import { motion } from "framer-motion";

interface FileListSkeletonProps {
  count?: number;
}

const shimmer = {
  hidden: { backgroundPosition: "-200% 0" },
  visible: {
    backgroundPosition: "200% 0",
    transition: {
      repeat: Infinity,
      duration: 1.5,
      ease: "linear" as const,
    },
  },
};

function SkeletonRow() {
  return (
    <div className="grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-4 px-4 py-3 border-b border-[#dadce0]">
      {/* Icon placeholder */}
      <div className="flex w-10 justify-center">
        <motion.div
          variants={shimmer}
          initial="hidden"
          animate="visible"
          className="h-5 w-5 rounded"
          style={{
            background:
              "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
            backgroundSize: "200% 100%",
          }}
        />
      </div>

      {/* Name placeholder */}
      <motion.div
        variants={shimmer}
        initial="hidden"
        animate="visible"
        className="h-4 w-48 rounded"
        style={{
          background:
            "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
          backgroundSize: "200% 100%",
        }}
      />

      {/* Modified date placeholder */}
      <motion.div
        variants={shimmer}
        initial="hidden"
        animate="visible"
        className="hidden md:block h-3 w-24 rounded"
        style={{
          background:
            "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
          backgroundSize: "200% 100%",
        }}
      />

      {/* Size placeholder */}
      <motion.div
        variants={shimmer}
        initial="hidden"
        animate="visible"
        className="h-3 w-16 rounded"
        style={{
          background:
            "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
          backgroundSize: "200% 100%",
        }}
      />

      {/* Actions placeholder */}
      <div className="w-8" />
    </div>
  );
}

export function FileListSkeleton({ count = 10 }: FileListSkeletonProps) {
  return (
    <div className="min-w-full">
      {/* Table Header Skeleton */}
      <div className="sticky top-0 z-10 border-b border-[#dadce0] bg-white/95 dark:bg-[var(--background-subtle)]/95 backdrop-blur-sm">
        <div className="grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-4 px-4 py-3">
          <span className="w-10" />
          <motion.div
            variants={shimmer}
            initial="hidden"
            animate="visible"
            className="h-3 w-12 rounded"
            style={{
              background:
                "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
              backgroundSize: "200% 100%",
            }}
          />
          <motion.div
            variants={shimmer}
            initial="hidden"
            animate="visible"
            className="hidden md:block h-3 w-20 rounded"
            style={{
              background:
                "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
              backgroundSize: "200% 100%",
            }}
          />
          <motion.div
            variants={shimmer}
            initial="hidden"
            animate="visible"
            className="h-3 w-16 rounded"
            style={{
              background:
                "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
              backgroundSize: "200% 100%",
            }}
          />
          <span className="w-8" />
        </div>
      </div>

      {/* Rows */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ staggerChildren: 0.05 }}
      >
        {Array.from({ length: count }).map((_, i) => (
          <SkeletonRow key={i} />
        ))}
      </motion.div>
    </div>
  );
}
