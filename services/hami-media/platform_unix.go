//go:build darwin || linux

package main

import (
	"fmt"
	"syscall"
	"time"
)

func readSocketReceiveBuffer(fd uintptr) (int, error) {
	return syscall.GetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_RCVBUF)
}

func m7hProcessCPUSeconds() (float64, error) {
	var usage syscall.Rusage
	if err := syscall.Getrusage(syscall.RUSAGE_SELF, &usage); err != nil {
		return 0, fmt.Errorf("read process CPU usage: %w", err)
	}
	user := float64(usage.Utime.Sec) + float64(usage.Utime.Usec)/float64(time.Second/time.Microsecond)
	system := float64(usage.Stime.Sec) + float64(usage.Stime.Usec)/float64(time.Second/time.Microsecond)
	return user + system, nil
}
