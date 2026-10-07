import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { formatCLP, formatDateShort } from "@/lib/format";
import CategoryIcon from "@/components/CategoryIcon";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, x: -20 },
  show: { opacity: 1, x: 0, transition: { type: "spring", stiffness: 260, damping: 20 } },
};

const MotionLink = motion(Link);

export default function RecentExpenses({ items }) {
  return (
    <div className="bg-[#f5f7fa] rounded-2xl p-7 shadow-md hover:shadow-lg transition-shadow duration-300">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-semibold font-heading text-slate-700">Gastos recientes</h3>
        <Link to="/gastos" className="text-sm text-sky-500 hover:text-sky-600 font-medium transition-colors">
          Ver todo
        </Link>
      </div>
      <motion.div variants={container} initial="hidden" animate="show" className="divide-y divide-slate-100">
        {items.map((e) => (
          <MotionLink
            key={e.id}
            to={`/gastos?expense=${e.id}`}
            variants={item}
            className="flex items-center py-3.5 group cursor-pointer hover:bg-slate-50 -mx-3 px-3 rounded-xl transition-colors"
          >
            <CategoryIcon category={e.category} color={e.color} className="mr-4" />
            <div className="flex-1 min-w-0">
              <div className="font-semibold font-heading text-slate-800 truncate">{e.merchant}</div>
              <div className="text-sm text-slate-400 truncate">{e.category} · {formatDateShort(e.date)}</div>
            </div>
            <div className="font-bold font-heading tabular-nums text-slate-800 ml-2">{formatCLP(e.amount)}</div>
          </MotionLink>
        ))}
        {items.length === 0 && (
          <div className="text-slate-400 text-sm py-8 text-center">Aún no hay gastos registrados</div>
        )}
      </motion.div>
    </div>
  );
}