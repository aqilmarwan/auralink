import React from 'react'
import Link from 'next/link';
import { GitHubLogoIcon } from '@radix-ui/react-icons'

const Footer = () => {
    return (
        <footer className="static inset-x-0 w-full bottom-0 my-4 select-none">
            <div className="md:flex md:items-center md:justify-between py-2 md:py-18 border-t border-gray-200"></div>
            <div className="flex h-[50px] py-2 px-12 items-center justify-center">
                <div className="flex flex-col w-full">
                    <div className="flex w-full lg:w-auto items-center justify-between">
                        <Link href="/" className="text-lg flex z-40 font-semibold">
                            <span>AuraLink</span>
                        </Link>
                    </div>
                    <div className="flex flex-row space-x-4">
                        <div className="flex items-center justify-between">
                            <span className="text-slate-500">Powered by
                                <span className="font-semibold text-slate-500"> Vercel </span>
                            </span>
                            <a
                                className="flex items-center hover:opacity-50"
                                href="https://github.com/aqilmarwan"
                                target="_blank"
                                rel="noreferrer"
                            >
                                <GitHubLogoIcon aria-setsize={30} />
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </footer>
    )
}

export default Footer

