# MOEX Bonds Analysis

## Overview

This is a comprehensive Streamlit web application for analyzing Russian government bonds from the Moscow Exchange (MOEX) using their ISS API. The application provides professional investment analysis with real-time data, advanced filtering, visual categorization, and export functionality for bond investment decision-making.

## Recent Changes (September 2025)
- **Live CBR Key Rate Integration**: Implemented real-time Central Bank of Russia API integration to fetch actual key rate via SOAP requests
- Enhanced UI with professional design and investment category classification
- Live key rate fetching with SOAP API calls to https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx using KeyRateXML method
- Debug output showing API call progress and rate extraction
- Fallback to CBR website scraping if SOAP API fails
- Implemented visual highlighting for target bonds (dynamic yield range based on actual CBR rate)
- Added next coupon date information from MOEX NEXTCOUPON field
- Q coefficient scaled to more readable values (divided by 100)
- Annual yield calculation with tax considerations: DEBIT = 10000 * (COUPONVALUE * (365 / COUPONPERIOD) * 0.87) / (PREVPRICE * LOTVALUE)
- Color-coded categories: Норма (target), Невыгодно (unprofitable), Риск (high risk) - now using live CBR rate
- Semi-transparent green highlighting (15% opacity) for target bonds
- Added FACEUNIT currency column with SUR->RUB conversion
- Replaced all "руб." references with "у.е." for universal currency units
- Integrated real-time Central Bank exchange rates (USD, EUR, CNY) display
- Added minimum coupon filter for enhanced bond selection criteria
- Added investment risk warning in sidebar

## User Preferences

Preferred communication style: Simple, everyday language.
UI preferences: Clean design with left-aligned metric headings, subtle visual indicators, professional color scheme.

## System Architecture

**Frontend Architecture**
- Built with Streamlit framework for rapid web application development
- Configured with wide layout and expandable sidebar for better user experience
- Uses pandas DataFrames for data manipulation and display
- Single-page application with real-time data fetching capabilities

**Data Processing Architecture**
- Direct API integration with MOEX ISS (Integrated Information System) 
- XML data parsing using pandas read_xml functionality
- Data merging strategy combining securities and market data from separate API endpoints
- Filter-based data processing with configurable parameters (coupon periods 25-35 days, lot values ≤1500 rubles)
- Q coefficient calculation for investment analysis: Q = (LOTVALUE × PREVPRICE) / COUPONVALUE

**Error Handling Strategy**
- Network timeout protection (30-second timeout)
- HTTP status code validation
- Graceful error messaging through Streamlit's error display system
- Data validation for required columns before processing

**Data Flow Design**
1. API request to MOEX for XML bond data
2. XML parsing into separate DataFrames (securities + marketdata)
3. DataFrame merging on security ID
4. Data type conversion and validation
5. Multi-criteria filtering
6. Coefficient calculation and analysis

## External Dependencies

**APIs**
- MOEX ISS API (iss.moex.com) - Primary data source for bond securities and market data
- XML endpoint: `/iss/engines/stock/markets/bonds/securities.xml`
- CBR SOAP API (www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx) - Real-time Central Bank key rate via KeyRateXML method
- CBR JSON API (cbr-xml-daily.ru) - Exchange rates data
- CBR Website (cbr.ru/hd_base/KeyRate/) - Fallback for key rate scraping

**Python Libraries**
- streamlit - Web application framework
- pandas - Data manipulation and analysis
- requests - HTTP client for API communication
- datetime - Date/time handling utilities

**Data Sources**
- Real-time bond securities data from Moscow Exchange
- Market data including pricing information
- Live Central Bank key rate from CBR SOAP API with XML parsing
- Real-time currency exchange rates from CBR JSON API
- No local database storage - relies entirely on live API data