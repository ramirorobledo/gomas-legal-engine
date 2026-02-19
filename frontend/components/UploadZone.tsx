"use client"

import React, { useState, useCallback } from 'react'
import { UploadCloud, File, AlertCircle, CheckCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'

interface UploadZoneProps {
    onUploadComplete: () => void
}

export function UploadZone({ onUploadComplete }: UploadZoneProps) {
    const [isDragging, setIsDragging] = useState(false)
    const [isUploading, setIsUploading] = useState(false)
    const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
    const [message, setMessage] = useState('')

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(true)
    }

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
    }

    const handleDrop = useCallback(async (e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0]
            await uploadFile(file)
        }
    }, [])

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            await uploadFile(e.target.files[0])
        }
    }

    const uploadFile = async (file: File) => {
        if (file.type !== 'application/pdf') {
            setUploadStatus('error')
            setMessage('Solo se permiten archivos PDF.')
            return
        }

        setIsUploading(true)
        setUploadStatus('idle')
        setMessage('')

        const formData = new FormData()
        formData.append('file', file)

        try {
            const response = await fetch('http://127.0.0.1:8000/upload', {
                method: 'POST',
                body: formData,
            })

            if (!response.ok) {
                throw new Error('Error en la subida')
            }

            setUploadStatus('success')
            setMessage(`Archivo ${file.name} subido correctamente.`)
            onUploadComplete() // Refresh list
        } catch (error) {
            console.error(error)
            setUploadStatus('error')
            setMessage('Hubo un error al subir el archivo.')
        } finally {
            setIsUploading(false)
            // Reset success status after 3 seconds
            setTimeout(() => {
                if (uploadStatus !== 'error') {
                    setUploadStatus('idle')
                    setMessage('')
                }
            }, 3000)
        }
    }

    return (
        <div className="w-full">
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                    "relative border-2 border-dashed rounded-xl p-8 transition-all duration-300 ease-in-out flex flex-col items-center justify-center cursor-pointer min-h-[200px]",
                    isDragging
                        ? "border-primary bg-primary/10 scale-[1.02]"
                        : "border-slate-700 hover:border-slate-500 hover:bg-slate-800/50"
                )}
            >
                <input
                    type="file"
                    accept=".pdf"
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    onChange={handleFileSelect}
                />

                <AnimatePresence mode="wait">
                    {isUploading ? (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center"
                        >
                            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mb-4"></div>
                            <p className="text-slate-400">Subiendo archivo...</p>
                        </motion.div>
                    ) : uploadStatus === 'success' ? (
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center text-green-500"
                        >
                            <CheckCircle className="w-12 h-12 mb-2" />
                            <p className="text-sm font-medium">{message}</p>
                        </motion.div>
                    ) : uploadStatus === 'error' ? (
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center text-red-500"
                        >
                            <AlertCircle className="w-12 h-12 mb-2" />
                            <p className="text-sm font-medium">{message}</p>
                        </motion.div>
                    ) : (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="flex flex-col items-center text-center"
                        >
                            <div className="p-4 bg-primary/10 rounded-full mb-4">
                                <UploadCloud className="w-8 h-8 text-primary" />
                            </div>
                            <h3 className="text-lg font-semibold text-slate-200 mb-1">Arrastra tu PDF aquí</h3>
                            <p className="text-sm text-slate-400">o haz clic para explorar</p>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    )
}
