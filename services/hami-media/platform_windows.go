//go:build windows

package main

import (
	"fmt"
	"syscall"
	"time"
)

func readSocketReceiveBuffer(fd uintptr) (int, error) {
	return syscall.GetsockoptInt(syscall.Handle(fd), syscall.SOL_SOCKET, syscall.SO_RCVBUF)
}

func m7hProcessCPUSeconds() (float64, error) {
	handle, err := syscall.GetCurrentProcess()
	if err != nil {
		return 0, fmt.Errorf("get current process handle: %w", err)
	}
	var creation, exit, kernel, user syscall.Filetime
	if err := syscall.GetProcessTimes(handle, &creation, &exit, &kernel, &user); err != nil {
		return 0, fmt.Errorf("read process CPU usage: %w", err)
	}
	return float64(user.Nanoseconds())/float64(time.Second) +
		float64(kernel.Nanoseconds())/float64(time.Second), nil
}

func readSFUHostSnapshotLive(baseline sfuHostSnapshot) (sfuHostSnapshot, error) {
	return baseline, fmt.Errorf("macOS live host snapshot is unavailable on Windows")
}

func readAudioSwapMiB() (used, free float64, returnErr error) {
	return 0, 0, fmt.Errorf("macOS swap accounting is unavailable on Windows")
}
