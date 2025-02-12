import time
import pytest
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Utility function to read the input file and extract registration numbers
def extract_reg_numbers(input_file):
    reg_numbers = []
    try:
        with open(input_file, 'r') as file:
            content = file.read()
            reg_numbers = re.findall(r'\b[A-Z]{2}[0-9]{2} [A-Z]{3}\b', content)  # Matches patterns like AD58 VNF, KT17 DLX
        logging.debug(f"Extracted registration numbers: {reg_numbers}")
    except Exception as e:
        logging.error(f"Error reading input file {input_file}: {e}")
    return reg_numbers


# Utility function to read the expected output from the output file
def read_expected_output(output_file):
    expected_output = {}
    try:
        with open(output_file, 'r') as file:
            lines = file.readlines()

            # Skip header and iterate over the rest of the lines
            for line in lines[1:]:  # Skip header
                # Skip empty lines
                if not line.strip():
                    continue

                # Split the line into parts
                parts = line.strip().split(',')

                # Check if the line contains the expected number of columns
                if len(parts) != 3:
                    logging.warning(f"Skipping malformed line: {line.strip()}")
                    continue

                # Normalize registration number by removing extra spaces
                reg_number = parts[0].strip().replace(' ', '')  # Remove any extra spaces
                car_details = {
                    'make_model': parts[1].strip(),
                    'year': parts[2].strip()
                }
                expected_output[reg_number] = car_details
        
        logging.debug(f"Expected output: {expected_output}")
    except Exception as e:
        logging.error(f"Error reading output file {output_file}: {e}")
    return expected_output


# WebDriver setup for using Chrome
def setup_driver():
    try:
        options = webdriver.ChromeOptions()
        # Running browser in visible mode (not headless)
        options.add_argument('start-maximized')  # Start the browser maximized
        options.add_argument('disable-infobars')  # Disable browser info bars
        options.add_argument('--disable-extensions')  # Disable extensions
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        # Use ChromeDriverManager to automatically download the driver
        driver_path = ChromeDriverManager().install()
        logging.debug(f"Using ChromeDriver located at: {driver_path}")

        # Initialize the Chrome WebDriver with the Service object
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        logging.error(f"Error setting up WebDriver: {e}")
        raise


# Function to get car details from motorway.co.uk based on registration number
def get_car_details_from_motorway(driver, reg_number):
    driver.get("https://www.motorway.co.uk/")
    logging.debug(f"Page source after loading: {driver.page_source}")  # Log the page source immediately after loading

    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'reg-input')))
    except TimeoutException:
        logging.error(f"Timed out waiting for the registration input field for {reg_number}")
        logging.debug(f"Page source at timeout: {driver.page_source}")  # Log the page source at timeout
        return None

    # Locate the input field and enter the registration number
    reg_input = driver.find_element(By.ID, 'reg-input')
    reg_input.clear()
    reg_input.send_keys(reg_number)
    reg_input.send_keys(Keys.RETURN)


    # Locate the 'Your vehicle registration' input field by its ID
registration_input = driver.find_element(By.ID, "registrationInputId")  # Replace with actual ID

# Enter the vehicle registration number
registration_input.send_keys("AD58 VNF")

# Locate the 'Value your car' button by its ID
value_button = driver.find_element(By.ID, "valueButtonId")  # Replace with actual ID

# Click the 'Value your car' button
value_button.click()

# Optionally, wait for the results to load
driver.implicitly_wait(10)

# Close the browser
driver.quit()

    # Retry mechanism to handle dynamic loading
    retries = 3
    while retries > 0:
        try:
            # Wait for the elements that confirm car details are loaded
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//h1[@class='vehicle-details__title']")))
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//li[contains(text(), 'Year')]//span")))
            logging.debug(f"Car details loaded for {reg_number}")
            break
        except TimeoutException:
            retries -= 1
            logging.warning(f"Retrying... {retries} attempts left for {reg_number}")
            if retries == 0:
                logging.error(f"Timed out waiting for car details for {reg_number}")
                logging.debug(f"Page source at failure: {driver.page_source}")  # Log the page source at failure
                return None
            time.sleep(3)  # Wait for 3 seconds before retrying

    # Now extract the details
    try:
        make_model = driver.find_element(By.XPATH, "//h1[@class='vehicle-details__title']").text
        year = driver.find_element(By.XPATH, "//li[contains(text(), 'Year')]//span").text
        logging.debug(f"Successfully retrieved details for {reg_number}: {make_model}, {year}")
        return {'make_model': make_model, 'year': year}
    except Exception as e:
        logging.error(f"Error extracting details for {reg_number}: {e}")
        logging.debug(f"Page source at failure: {driver.page_source}")  # Log the page source at failure
        return None


# Pytest test case to check car details
@pytest.mark.parametrize("reg_number", extract_reg_numbers('/Users/ds/Desktop/car_input.txt'))
def test_car_details(reg_number):
    try:
        driver = setup_driver()
        expected_output = read_expected_output('/Users/ds/Desktop/car_output.txt')

        if reg_number not in expected_output:
            pytest.fail(f"Registration number {reg_number} not found in expected output.")

        expected_details = expected_output[reg_number]

        # Fetch actual details from the website
        actual_details = get_car_details_from_motorway(driver, reg_number)

        if actual_details:
            # Compare the expected and actual details
            assert actual_details['make_model'] == expected_details['make_model'], f"Mismatch in make/model for {reg_number}"
            assert actual_details['year'] == expected_details['year'], f"Mismatch in year for {reg_number}"
        else:
            pytest.fail(f"Failed to retrieve car details for {reg_number}")
    except Exception as e:
        logging.error(f"Test failed for {reg_number}: {e}")
        pytest.fail(f"Test failed for {reg_number} due to error: {e}")
    finally:
        driver.quit()
