# Terminology and Definitions

The backend API uses a number of shorthands and mnemonics. This file documents their semantics

# Asset statuses

In the asset JSON, the `status` field has the following shorthands:

| Status | Meaning                                                  |
| ------ | -------------------------------------------------------- |
| A      | Active assets with standard scanning                     |
| AH     | Active assets with comprehensive scanning                |
| AL     | Active assets that are only scanned for asset discovery  |
| F      | Frozen assets. They are not scanned                      |

# Risk statuses

| Status | Meaning                                                  |
| ------ | -------------------------------------------------------- |
| A      | Active assets with standard scanning                     |
| AH     | Active assets with comprehensive scanning                |
| AL     | Active assets that are only scanned for asset discovery  |
| F      | Frozen assets. They are not scanned                      |

 
 
 
 Triage                      string = "T"
	TriageInfo                  string = "TI"
	TriageLow                   string = "TL"
	TriageMedium                string = "TM"
	TriageHigh                  string = "TH"
	TriageCritical              string = "TC"
	Open                        string = "O"
	OpenInfo                    string = "OI"
	OpenLow                     string = "OL"
	OpenMedium                  string = "OM"
	OpenHigh                    string = "OH"
	OpenCritical                string = "OC"
	Closed                      string = "C"
	ClosedInfo                  string = "CI"
	ClosedLow                   string = "CL"
	ClosedMedium                string = "CM"
	ClosedHigh                  string = "CH"
	ClosedCritical              string = "CC"
	ClosedInfoFalsePositive     string = "CIF"
	ClosedLowFalsePositive      string = "CLF"
	ClosedMediumFalsePositive   string = "CMF"
	ClosedHighFalsePositive     string = "CHF"
	ClosedCriticalFalsePositive string = "CCF"
	ClosedInfoRejected          string = "CIR"
	ClosedLowRejected           string = "CLR"
	ClosedMediumRejected        string = "CMR"
	ClosedHighRejected          string = "CHR"
	ClosedCriticalRejected      string = "CCR"
