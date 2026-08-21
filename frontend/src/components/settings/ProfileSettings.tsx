"use client";

import { User, Mail } from "lucide-react";

export default function ProfileSettings() {
    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">

            <div className="mb-6">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                    Profile
                </h2>

                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    Manage your personal information.
                </p>
            </div>

            {/* Avatar */}
            <div className="mb-8 flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-200 dark:bg-slate-700">
                    <User
                        size={28}
                        className="text-slate-500 dark:text-slate-300"
                    />
                </div>

                <div>
                    <p className="font-medium text-slate-900 dark:text-white">
                        Profile Photo
                    </p>

                    <button className="mt-1 text-sm font-medium text-blue-600 hover:text-blue-700">
                        Change photo
                    </button>
                </div>
            </div>

            {/* Name */}
            <div className="mb-5">
                <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Full Name
                </label>

                <div className="relative">
                    <User
                        size={18}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />

                    <input
                        type="text"
                        placeholder="Your name"
                        className="w-full rounded-xl border border-slate-200 bg-white px-10 py-3 text-sm outline-none transition focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    />
                </div>
            </div>

            {/* Email */}
            <div className="mb-8">
                <label className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Email
                </label>

                <div className="relative">
                    <Mail
                        size={18}
                        className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                    />

                    <input
                        type="email"
                        placeholder="your@email.com"
                        className="w-full rounded-xl border border-slate-200 bg-white px-10 py-3 text-sm outline-none transition focus:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    />
                </div>
            </div>

            <div className="flex justify-end">
                <button className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200">
                    Save Changes
                </button>
            </div>
        </div>
    );
}