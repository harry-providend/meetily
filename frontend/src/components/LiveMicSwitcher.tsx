"use client";

import { useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { toast } from 'sonner';
import { Mic, Loader2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { recordingService } from '@/services/recordingService';
import Analytics from '@/lib/analytics';

interface AudioDevice {
  name: string;
  device_type: string;
}

interface LiveMicSwitcherProps {
  /** Current mic, in either the bare or the "Name (input)" form config stores. */
  currentMicName?: string | null;
  /** Receives the bare device name. */
  onSwitched?: (deviceName: string) => void;
}

/** Config stores devices as "Name (input)"; the backend matches on the bare name. */
function toBareName(name: string | null | undefined): string | null {
  if (!name) return null;
  return name.replace(/\s*\((input|output)\)$/i, '');
}

/**
 * Compact microphone picker for the recording pill. Deliberately separate from
 * DeviceSelection, which is a full settings panel and starts audio-level monitoring
 * that would contend with the live capture.
 */
export function LiveMicSwitcher({ currentMicName, onSwitched }: LiveMicSwitcherProps) {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [isSwitching, setIsSwitching] = useState(false);
  const [activeMic, setActiveMic] = useState<string | null>(toBareName(currentMicName));

  useEffect(() => {
    setActiveMic(toBareName(currentMicName));
  }, [currentMicName]);

  const fetchDevices = useCallback(async () => {
    try {
      const all = await invoke<AudioDevice[]>('get_audio_devices');
      setDevices(all.filter((d) => d.device_type.toLowerCase() === 'input'));
    } catch (error) {
      console.error('Failed to list microphones:', error);
    }
  }, []);

  const handleSelect = useCallback(async (deviceName: string) => {
    if (deviceName === activeMic || isSwitching) return;

    setIsSwitching(true);
    try {
      await recordingService.switchMicrophoneDevice(deviceName);
      setActiveMic(deviceName);
      onSwitched?.(deviceName);

      toast.success(`Switched to ${deviceName}`, {
        description: 'A moment of audio may be missing while the microphone changes.',
      });
      await Analytics.trackFeatureUsed('switch_microphone_live');
    } catch (error) {
      console.error('Failed to switch microphone:', error);
      toast.error('Could not switch microphone', {
        description: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setIsSwitching(false);
    }
  }, [activeMic, isSwitching, onSwitched]);

  return (
    <DropdownMenu onOpenChange={(open) => open && fetchDevices()}>
      <Tooltip>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <button
              disabled={isSwitching}
              className="w-10 h-10 flex items-center justify-center rounded-full text-gray-600 hover:bg-gray-100 disabled:text-gray-400 transition-colors"
            >
              {isSwitching ? <Loader2 size={16} className="animate-spin" /> : <Mic size={16} />}
            </button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent>
          <p>{activeMic ? `Microphone: ${activeMic}` : 'Change microphone'}</p>
        </TooltipContent>
      </Tooltip>

      <DropdownMenuContent align="center" side="top">
        <DropdownMenuLabel>Microphone</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {devices.length === 0 ? (
          <DropdownMenuItem disabled>No microphones found</DropdownMenuItem>
        ) : (
          devices.map((device) => (
            <DropdownMenuItem
              key={device.name}
              onClick={() => handleSelect(device.name)}
              className={device.name === activeMic ? 'font-medium' : ''}
            >
              {device.name}
              {device.name === activeMic && <span className="ml-2 text-xs">✓</span>}
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
