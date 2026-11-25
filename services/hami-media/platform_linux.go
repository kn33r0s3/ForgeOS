//go:build linux

package main

import "errors"

// Linux CI exercises the Pion loopback media path, not the macOS host
// watchdog. Do not substitute Linux metrics for the macOS pressure contract.
func readSFUHostSnapshotLive(baseline sfuHostSnapshot) (sfuHostSnapshot, error) {
	return baseline, errors.New("macOS live host snapshot is unavailable on Linux")
}

func readAudioSwapMiB() (used, free float64, returnErr error) {
	return 0, 0, errors.New("macOS swap accounting is unavailable on Linux")
}
