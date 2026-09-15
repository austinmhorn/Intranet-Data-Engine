package main

import (
	"Intranet-Data-Engine/notionapi" // Matches `go.mod`
	"encoding/csv"
	"fmt"
	"os"
	// "time"
)

var outputFile string = "data/notion_data.csv"

var powerUsers = map[string]bool{
	"BR948": true,
	"BR568": true,
	"BR861": true,
	"BR542": true,
}

func isPowerUser(id string) bool {
	return powerUsers[id]
}

func getUniquePassword(id string) string {
	password := "#" + id
	return password
}

func main() {
	// Load configuration first
	err := notionapi.LoadConfig()
	if err != nil {
		fmt.Println("❌ Error loading config:", err)
		return
	}

	fmt.Println("🚀 Fetching Notion Data...")
	data, err := notionapi.FetchNotionData()
	if err != nil {
		fmt.Println("❌ Error fetching data from Notion:", err)
		return
	}

	totalEntries := len(data)
	if totalEntries == 0 {
		fmt.Println("❌ No data found in Notion.")
		return
	}

	fmt.Printf("✅ Successfully retrieved %d entries from Notion.\n", totalEntries)

	// Save data to CSV
	csvFileName := outputFile
	csvFile, err := os.Create(csvFileName)
	if err != nil {
		fmt.Println("❌ ERROR: Creating CSV file:", err)
		return
	}
	defer csvFile.Close()

	writer := csv.NewWriter(csvFile)
	defer writer.Flush()

	headers := []string{
		"Username",
		"Email Address",
		"User ID",
		"Last Name",
		"First Name",
		"Active",
		"Password",
		"Authentication Type",
		"Profile Type",
		"Forced Password Reset",
		"Department",
		"Location",
		"Company",
		"Title",
		"Start Date",
		"End Date",
		"Supervisor",
		"Supervisor Employee ID",
	}
	writer.Write(headers)

	// Process each entry
	for i, entry := range data {
		props, ok := entry["properties"].(map[string]interface{})
		if !ok {
			fmt.Printf("⚠️ Skipping entry %d: Invalid properties format.\n", i+1)
			continue
		}

		emailStr := notionapi.GetFormulaTextValue(props, "Email (As Text)")
		employeeIDStr := notionapi.GetCleanPlainTextValue(props, "Employee ID")
		userNameStr := employeeIDStr
		lastNameStr := notionapi.GetFormulaTextValue(props, "Last Name")
		firstNameStr := notionapi.GetFormulaTextValue(props, "First Name")
		activeStr := notionapi.GetStatus(props, "Status")
		passwordStr := getUniquePassword(employeeIDStr)
		authenticationTypeStr := "Local Login"
		profileTypeStr := "Intranet User"
		forcedPasswordReset := "TRUE"
		departmentStr := notionapi.GetRollupSelectValue(props, "Department")
		locationStr := notionapi.GetFormulaTextValue(props, "Property (Cleaned)")
		companyStr := notionapi.GetSelectValue(props, "Company")
		titleStr := notionapi.GetRollupFormulaString(props, "Title (As Text)")
		startDateStr := notionapi.GetDateValue(props, "Hire Date")
		endDateStr := notionapi.GetDateValue(props, "Term Date")
		supervisorStr := notionapi.GetRollupFormulaString(props, "Supervisor (As Text)")
		supervisorEmployeeIDStr := notionapi.GetRollupPlainText(props, "Supervisor Employee ID")

		// Configure 'Active' column
		if activeStr == "Active" {
			activeStr = "TRUE"
		} else {
			activeStr = "FALSE"
		}

		// Assign 'Power User' to approved User IDs
		if isPowerUser(employeeIDStr) {
			profileTypeStr = "Power User"
		}

		row := []string{
			userNameStr,
			emailStr,
			employeeIDStr,
			lastNameStr,
			firstNameStr,
			activeStr,
			passwordStr,
			authenticationTypeStr,
			profileTypeStr,
			forcedPasswordReset,
			departmentStr,
			locationStr,
			companyStr,
			titleStr,
			startDateStr,
			endDateStr,
			supervisorStr,
			supervisorEmployeeIDStr[0],
		}
		writer.Write(row)

		// Print progress
		// fmt.Printf("📊 Progress: %d/%d (%.2f%%)\n", i+1, totalEntries, float64(i+1)/float64(totalEntries)*100)
	}

	fmt.Printf("✅ Data successfully written to %s!\n", csvFileName) // Save data to CSV
}
