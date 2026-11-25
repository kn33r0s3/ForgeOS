//go:build darwin

package main

import (
	"encoding/binary"
	"fmt"
	"syscall"
	"time"
)

// FIX 30: readSFUHostSnapshotLive is the in-run macOS host watchdog reader.
// The preflight reader spawns four subprocesses per call (sysctl pressure,
// sysctl vm.swapusage, vm_stat, df); fired once a second inside a streaming
// cell, those forks stalled the whole process 50-120 ms per tick. This reader
// uses direct syscalls for pressure, swap and disk, avoiding that stall.
// MemFreeMiB/Swapouts/Pageouts are carried forward from the preflight
// baseline because macOS exposes them only through Mach host_statistics.
func readSFUHostSnapshotLive(baseline sfuHostSnapshot) (sfuHostSnapshot, error) {
	snapshot := baseline
	snapshot.ObservedAt = time.Now().UTC()
	pressure, err := syscall.SysctlUint32("kern.memorystatus_vm_pressure_level")
	if err != nil {
		return snapshot, fmt.Errorf("read macOS VM pressure: %w", err)
	}
	snapshot.PressureLevel = int(pressure)
	snapshot.SwapUsedMiB, snapshot.SwapFreeMiB, err = readAudioSwapMiB()
	if err != nil {
		return snapshot, err
	}
	snapshot.SwapTotalMiB = snapshot.SwapUsedMiB + snapshot.SwapFreeMiB
	var stat syscall.Statfs_t
	if err := syscall.Statfs(".", &stat); err != nil {
		return snapshot, fmt.Errorf("read free disk space: %w", err)
	}
	snapshot.FreeDiskBytes = stat.Bavail * uint64(stat.Bsize)
	return snapshot, nil
}

// FIX 30: readAudioSwapMiB reads macOS swap usage through sysctl(2), avoiding
// a subprocess on each watchdog tick. The raw xsw_usage fields are uint64
// byte counts: total, available, used, then page size and encrypted flag.
func readAudioSwapMiB() (used, free float64, returnErr error) {
	raw, err := syscall.Sysctl("vm.swapusage")
	if err != nil {
		return 0, 0, fmt.Errorf("read macOS swap usage: %w", err)
	}
	rawBytes := []byte(raw)
	if len(rawBytes) < 24 {
		return 0, 0, fmt.Errorf("read macOS swap usage: short xsw_usage (%d bytes)", len(rawBytes))
	}
	freeBytes := binary.LittleEndian.Uint64(rawBytes[8:16])
	usedBytes := binary.LittleEndian.Uint64(rawBytes[16:24])
	used = float64(usedBytes) / (1024 * 1024)
	free = float64(freeBytes) / (1024 * 1024)
	return used, free, nil
}
