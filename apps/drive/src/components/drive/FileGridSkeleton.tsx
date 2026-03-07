"use client";

import { motion } from "framer-motion";

interface FileGridSkeletonProps {
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

function SkeletonCard() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col items-center rounded-lg border border-[#dadce0] bg-white dark:bg-[var(--background-subtle)] p-4"
    >
      {/* Icon placeholder */}
      <motion.div
        variants={shimmer}
        initial="hidden"
        animate="visible"
        className="mb-4 h-12 w-12 rounded-lg"
        style={{
          background:
            "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
          backgroundSize: "200% 100%",
        }}
      />

      {/* Name placeholder */}
      <motion.div
        variants={shimmer}
        initial="hidden"
        animate="visible"
        className="h-4 w-24 rounded"
        style={{
          background:
            "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
          backgroundSize: "200% 100%",
        }}
      />

      {/* Meta info placeholder */}
      <motion.div
        variants={shimmer}
        initial="hidden"
        animate="visible"
        className="mt-2 h-3 w-16 rounded"
        style={{
          background:
            "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
          backgroundSize: "200% 100%",
        }}
      />
    </motion.div>
  );
}

export function FileGridSkeleton({ count = 12 }: FileGridSkeletonProps) {
  return (
    <div className="p-6">
      {/* Folders section header */}
      <div className="mb-4 flex items-center gap-2">
        <span className="h-px flex-1 bg-gradient-to-r from-[#dadce0] to-transparent" />
        <motion.div
          variants={shimmer}
          initial="hidden"
          animate="visible"
          className="h-4 w-16 rounded"
          style={{
            background:
              "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
            backgroundSize: "200% 100%",
          }}
        />
        <span className="h-px flex-1 bg-gradient-to-l from-[#dadce0] to-transparent" />
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
        {Array.from({ length: count }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}
