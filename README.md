# Dublin Bikes - Group 13 of COMP30830

## Title Page

* Product: Dublin Bikes
* Version: TBC
* Date: TBC

## Table of Contents
- [1. Features](#1-features)
- [2. Getting Started](#2-getting-started)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [3. Usage](#3-usage)
- [4. Development Guidelines](#4-development-guidelines)
- [(TBC)Testing]()
- [(TBC)License]()
- [(TBC)Contact]()

---

## 1. Features

### **Feature and Functionality:**
- Bike station real-time availability and prediction
- Nearby weather information
- Login to save your favorite stops

### **Functional Map**
* Main:
    - Map showing stations, availability
    - Fetch user device location
    - Predict station availability
    - Reloate self

* Account:
    - Signup
    - Login
    - Forget password
    - Change password
    - My subscription/payment

* Overview:
    - Service tutorial
    - Safety guide
    - Subscription

---

## 2. Getting Started

### **Installation:**
To get started with **Dublin Bikes - Group 13 of COMP30830**, follow these steps:
1. Clone the repository:
   ```bash
   git clone https://github.com/kksskkkksskkkks/COMP30830_Project/tree/develop
   ```

2. Navigate to the project directory:
   ```bash
   cd project-name
   ```

3. Install the dependencies:
   ```bash
   npm install  # or pip install -r requirements.txt, etc.
   ```

 
### **Configuration:** 
To configure the project, create a `.env` file in the root directory and add the following environment variables:

```env
# Database (TBD)

# Bike
JCKEY=your_jcdecaux_key
CONTRACT=dublin
STATIONS_URI=https://api.jcdecaux.com/vls/v1/stations

# Weather
OWKEY=your_openwether_api_key
CURRENT_URI=https://api.openweathermap.org/data/2.5/weather
```

---

## 3. (TBC) Usage
Here’s how to use **Dublin Bikes - Group 13 of COMP30830**:

1. Run the project:
   ```bash
   npm start  # or python main.py, etc.
   ```

2. Access the application at `http://localhost:3000`.


---

## 4. Development Guidelines

**Coding Standards:**
A summary of the coding best practices:

**Fundamental Design Principles**
*   **Keep functions short and files numerous:** Avoid creating "god classes" or excessively long files. Break logic down into many short functions and modular files.
*   **Maximize Cohesion:** Design modules and functions to focus on a single, well-defined task or responsibility, making them easier to test and maintain.
*   **Ensure Decoupling:** Minimize interdependencies between modules so the system remains flexible and easier to change.
*   **Practice Information Hiding:** Do not use global variables whenever possible. Restrict access to data and components strictly through well-defined interfaces.
*   **Separation of Concerns:** Keep your architecture clean by strictly separating logic (e.g., Python code) from presentation layers (e.g., HTML using Jinja2 templates).

**Naming Conventions and Coding Styles**
*   **Use descriptive, explicit naming:** Choose meaningful names that reflect the variable or function's purpose. Avoid single-letter variables (except for basic loop counters). Function names should typically start with a verb (e.g., `calculate_total`).
*   **Python (PEP 8) styling:** Use `snake_case` for variables and functions, `PascalCase` for class definitions, and `UPPER_SNAKE_CASE` for constants. 
*   **JavaScript styling:** Use `camelCase` for variables and functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants, and `kebab-case` for filenames.
*   **Make variable types explicit:** In Python, define the expected input and return types using type hinting (e.g., `def add(a: int) -> int:`) to improve code clarity and catch errors early with static tools like mypy.

**Documentation and Commenting**
*   **Explain the "why", not just the "what":** Comments should clarify the intent of the code, any unusual behavior, edge-case handling, and architectural decisions.
*   **Use standard documentation blocks:** Comment all functions, classes, and modules detailing their arguments, return values, and exceptions raised. Use PEP 257 standards for Python and JSDoc for JavaScript.
*   **Flag incomplete code:** Mark unfinished segments clearly using standard markers like `TODO`.

**Version Control (Git) Practices**
*   **Commit early and often:** Work in small chunks and commit frequently to avoid massive merge conflicts and effectively track changes.
*   **Make single-purpose commits:** Do not bundle multiple unrelated features or bug fixes into a single commit.
*   **Use branches properly:** Never edit production code directly. Use feature branches to isolate environments for every change, no matter how small, and merge them via Pull Requests.
*   **Exclude generated files:** Always use a `.gitignore` file to ensure you do not commit system-generated, temporary, or easily re-generated files to your repository.

**Error Handling and Logging**
*   **Handle errors gracefully:** Employ `try-catch` blocks in JS and route aborts (e.g., `abort(404)`) in Python to deal with unexpected inputs or failures.

**Web Development & Architecture**
*   **Protect your API and Secret Keys:** **Never** commit API keys or secret keys to code repositories. Store them as environment variables and restrict their usage via IP addresses or specific websites.
*   **Use Flask Contexts securely:** Utilize Flask's `g` variable to temporarily store data (like database connections) within a single request, and `session` dictionaries for retaining data across multiple requests.