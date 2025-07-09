# app/api/utils/background_tasks.py
# ==================================
"""
Centralized background task execution utilities
Provides all background processing functions for web scraping and report generation
"""

import os
import time
import shutil
import tempfile
import logging

# Import from your structure
from app.services.project.export_project_details import find_project_directory, find_report_workbook, update_workbook_with_summary, create_workbook, insert_project_data, insert_client_data, save_workbook
from app.services.project.project_manager import get_project_by_code
from app.services.asce.asce_hazard_summary import ASCEScraper 
from app.services.asce.asce_hazard_report import ASCEReportScraper
from app.services.soil.soil_scraper import WebSoilSurveyScraper, SoilScraperConfig
from app.core.models import Project, ASCESummaryData, WindData, SeismicData, IceData, SnowData
from app.api.utils.progress_tracking import ProgressTracker, SingleStepProgressTracker, progress_tracker

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# BACKGROUND EXECUTION FUNCTIONS
# =============================================================================
def _execute_individual_asce_summary_with_progress(session_id, project_data, address, asce_options):
    """
    Execute individual ASCE Summary with progress tracking.
    Note: This runs in a background thread without Flask request context.
    """
    tracker = SingleStepProgressTracker(session_id, 'ASCE Summary')
    project_number = project_data['code']
    
    try:
        # Step 1: Check if AHJ Report exists
        tracker.update_progress(10, 'Checking AHJ report availability...')
        
        find_result = find_report_workbook(project_number)
        if isinstance(find_result, tuple) and len(find_result) == 2:
            workbook_exists, result = find_result
        else:
            workbook_exists = False
            result = "Unexpected function return format"
        
        # If workbook doesn't exist, create it first
        if not workbook_exists:
            logger.info(f"AHJ Report not found for project {project_number}. Creating new report.")
            tracker.update_progress(20, 'Creating AHJ report...')
            
            # Create a minimal workbook to hold the ASCE summary
            workbook = create_workbook()
            insert_project_data(workbook.active, project_data)
            
            # Create minimal client data if not available
            client_data = {
                'client_name': 'N/A',
                'client_email': 'N/A', 
                'client_phone': 'N/A',
                'street1': '',
                'street2': '',
                'city': '',
                'state': '',
                'zip_code': ''
            }
            insert_client_data(workbook.active, client_data)
            
            # Save the workbook
            workbook_path = save_workbook(workbook, project_number)
            if not workbook_path:
                tracker.set_error('Failed to create AHJ Report for ASCE Summary')
                return
                
            logger.info(f"Created minimal AHJ report for ASCE Summary at: {workbook_path}")
        
        # Step 2: Initialize ASCE scraper
        tracker.update_progress(40, 'Initializing ASCE summary scraper...')
        scraper = ASCEScraper()
        
        try:
            # Step 3: Execute scraping
            tracker.update_progress(60, 'Extracting ASCE summary data...')
            
            success, error_msg, summary_data = scraper.run_scraping_process(
                address=address,
                standard_version=asce_options['standard_version'],
                risk_category=asce_options['risk_category'],
                soil_class=asce_options['soil_class']
            )
            
            if not success:
                tracker.set_error(f'Failed to extract ASCE summary: {error_msg}')
                return
            
            # Step 4: Save summary to workbook
            tracker.update_progress(80, 'Saving summary to AHJ report...')
            
            success, result = update_workbook_with_summary(project_number, summary_data)
            if not success:
                tracker.set_error(f'Failed to save summary to workbook: {result}')
                return
            
            # Step 5: Store summary data globally for later retrieval
            tracker.update_progress(90, 'Preparing summary display...')
            
            # Store summary data in Redis or global progress tracker for retrieval
            # Since we can't access Flask session from background thread
            summary_dict = {
                'wind_data': {
                    'wind_speed': summary_data.wind_data.wind_speed,
                    'ten_year_mri': summary_data.wind_data.ten_year_mri,
                    'twenty_five_year_mri': summary_data.wind_data.twenty_five_year_mri,
                    'fifty_year_mri': summary_data.wind_data.fifty_year_mri,
                    'hundred_year_mri': summary_data.wind_data.hundred_year_mri,
                    'unit': summary_data.wind_data.unit
                },
                'seismic_data': vars(summary_data.seismic_data),
                'ice_data': vars(summary_data.ice_data),
                'snow_data': vars(summary_data.snow_data)
            }
            
            # Store in the progress tracker for retrieval by the display route
            if session_id in progress_tracker:
                progress_tracker[session_id]['summary_data'] = summary_dict
                progress_tracker[session_id]['project_data'] = project_data
            
            # Mark as completed
            tracker.update_progress(100, 'ASCE Summary completed successfully!', 'completed')
            
            logger.info(f"ASCE Summary generation completed successfully for project {project_number}")
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in individual ASCE summary generation: {str(e)}")
        tracker.set_error(str(e))

#######################################################

def _execute_asce_full_report_with_progress(project_number, address, asce_options, project_dir, tracker, step_index):
    """Execute ASCE Full Report with progress updates - FIXED for SingleStepProgressTracker"""
    try:
        # Set up file paths
        report_dir = os.path.join(project_dir, "Project_Info", "ASCE_Hazard_Report")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"ASCE_Report_{project_number}_{timestamp}.pdf"
        destination_path = os.path.join(report_dir, filename)
        
        # Initialize scraper
        if isinstance(tracker, SingleStepProgressTracker):
            # For individual reports - use update_progress method
            tracker.update_progress(10, 'Initializing ASCE scraper...')
        else:
            # For unified reports - use update_step method
            tracker.update_step(step_index, 'in_progress', 10, 'Initializing ASCE scraper...')
        
        scraper = ASCEReportScraper()
        
        try:
            # Update progress during scraping
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(30, 'Accessing ASCE website...')
            else:
                tracker.update_step(step_index, 'in_progress', 30, 'Accessing ASCE website...')
            
            # Execute scraping with progress callbacks
            success, error_msg, temp_path = scraper.run_report_download(
                address=address,
                standard_version=asce_options['standard_version'],
                risk_category=asce_options['risk_category'],
                soil_class=asce_options['soil_class']
            )
            
            if not success:
                return {'success': False, 'message': error_msg, 'path': None}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(80, 'Saving ASCE report...')
            else:
                tracker.update_step(step_index, 'in_progress', 80, 'Saving ASCE report...')
            
            # Copy to final destination
            shutil.copy2(temp_path, destination_path)
            os.remove(temp_path)
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(95, 'ASCE report saved successfully')
            else:
                tracker.update_step(step_index, 'in_progress', 95, 'ASCE report saved successfully')
            
            logger.info(f"ASCE Full Report saved to: {destination_path}")
            return {
                'success': True,
                'message': 'ASCE Full Report generated successfully',
                'path': destination_path
            }
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in _execute_asce_full_report_with_progress: {str(e)}")
        return {'success': False, 'message': str(e), 'path': None}

#########################################################################

def _execute_asce_summary_with_progress(project_number, address, asce_options, tracker, step_index):
    """Execute ASCE Summary with progress updates - FIXED for SingleStepProgressTracker"""
    try:
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(10, 'Checking AHJ report availability...')
        else:
            tracker.update_step(step_index, 'in_progress', 10, 'Checking AHJ report availability...')
        
        # Check if AHJ Report exists
        find_result = find_report_workbook(project_number)
        
        if isinstance(find_result, tuple) and len(find_result) == 2:
            workbook_exists, result = find_result
        else:
            workbook_exists = False
        
        if not workbook_exists:
            return {
                'success': False,
                'message': f'AHJ Report not found for project {project_number}',
                'data': None
            }
        
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(30, 'Initializing ASCE summary scraper...')
        else:
            tracker.update_step(step_index, 'in_progress', 30, 'Initializing ASCE summary scraper...')
        
        # Initialize scraper
        scraper = ASCEScraper()
        
        try:
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(50, 'Extracting ASCE summary data...')
            else:
                tracker.update_step(step_index, 'in_progress', 50, 'Extracting ASCE summary data...')
            
            # Execute scraping
            success, error_msg, summary_data = scraper.run_scraping_process(
                address=address,
                standard_version=asce_options['standard_version'],
                risk_category=asce_options['risk_category'],
                soil_class=asce_options['soil_class']
            )
            
            if not success:
                return {'success': False, 'message': error_msg, 'data': None}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(80, 'Saving summary to AHJ report...')
            else:
                tracker.update_step(step_index, 'in_progress', 80, 'Saving summary to AHJ report...')
            
            # Save to AHJ report
            success, result = update_workbook_with_summary(project_number, summary_data)
            
            if not success:
                return {'success': False, 'message': f'Failed to save summary: {result}', 'data': summary_data}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(95, 'ASCE summary saved to AHJ report')
            else:
                tracker.update_step(step_index, 'in_progress', 95, 'ASCE summary saved to AHJ report')
            
            return {
                'success': True,
                'message': 'ASCE Summary generated and saved',
                'data': summary_data
            }
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in _execute_asce_summary_with_progress: {str(e)}")
        return {'success': False, 'message': str(e), 'data': None}


#########################################################################

def _execute_individual_asce_report_with_progress(session_id, project_data, address, asce_options):
    """Execute individual ASCE report with progress tracking - FIXED"""
    tracker = SingleStepProgressTracker(session_id, 'ASCE Full Report')
    project_number = project_data['code']
    
    try:
        # Ensure project directory exists
        tracker.update_progress(10, 'Setting up project directories...')
        project_dir = _ensure_project_directory_structure(project_number)
        if not project_dir:
            tracker.set_error(f'Failed to create/access project directory for {project_number}')
            return
        
        # Execute ASCE report generation
        tracker.update_progress(30, 'Starting ASCE report generation...')
        result = _execute_asce_full_report_with_progress(
            project_number, address, asce_options, project_dir, tracker, 0
        )
        
        if result['success']:
            tracker.update_progress(100, 'ASCE Full Report completed successfully!', 'completed')
        else:
            tracker.set_error(result['message'])
            
    except Exception as e:
        logger.error(f"Error in individual ASCE report generation: {str(e)}")
        tracker.set_error(str(e))
        
###################################################################

def _ensure_project_directory_structure(project_number):
    """
    Ensure all required project directories exist.
    
    Args:
        project_number (str): The project number/code
        
    Returns:
        str: Project directory path if successful, None if failed
    """
    try:
        # Find the main project directory
        project_dir = find_project_directory(project_number)
        if not project_dir:
            logger.error(f'Project directory not found for project code: {project_number}')
            return None

        # Create the Project_Info directory structure if it doesn't exist
        project_info_dir = os.path.join(project_dir, "Project_Info")
        
        # Define all required subdirectories
        required_dirs = [
            project_info_dir,
            os.path.join(project_info_dir, "AHJ_Report"),
            os.path.join(project_info_dir, "ASCE_Hazard_Report"),
            os.path.join(project_info_dir, "USDA_Soil_Reports"),
            os.path.join(project_info_dir, "Archived_AHJ_Reports")
        ]
        
        # Create all directories
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"Created directory: {dir_path}")
        
        logger.info(f"Project directory structure verified/created for project: {project_number}")
        return project_dir
        
    except Exception as e:
        logger.error(f"Error creating project directory structure: {str(e)}")
        return None

##########################################################################

def _execute_individual_soil_survey_with_progress(session_id, project_data, address):
    """Execute individual soil survey with progress tracking - FIXED"""
    tracker = SingleStepProgressTracker(session_id, 'USDA Soil Survey')
    project_number = project_data['code']
    
    try:
        # Ensure project directory exists
        tracker.update_progress(10, 'Setting up project directories...')
        project_dir = _ensure_project_directory_structure(project_number)
        if not project_dir:
            tracker.set_error(f'Failed to create/access project directory for {project_number}')
            return
        
        # Execute soil survey generation
        tracker.update_progress(30, 'Starting soil survey generation...')
        result = _execute_soil_survey_with_progress(
            project_number, address, project_dir, tracker, 0
        )
        
        if result['success']:
            tracker.update_progress(100, f'Generated {len(result["paths"])} soil reports successfully!', 'completed')
        else:
            tracker.set_error(result['message'])
            
    except Exception as e:
        logger.error(f"Error in individual soil survey generation: {str(e)}")
        tracker.set_error(str(e))

############################################################################

def _execute_soil_survey_with_progress(project_number, address, project_dir, tracker, step_index):
    """Execute Soil Survey with progress updates - FIXED for SingleStepProgressTracker"""
    temp_download_dir = None
    
    try:
        # Set up directories
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(10, 'Setting up soil survey directories...')
        else:
            tracker.update_step(step_index, 'in_progress', 10, 'Setting up soil survey directories...')
            
        report_dir = os.path.join(project_dir, "Project_Info", "USDA_Soil_Reports")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        # Create file paths
        linear_filename = f"Linear_Extensibility_{project_number}_{timestamp}.pdf"
        soil_class_filename = f"Unified_Soil_Classification_{project_number}_{timestamp}.pdf"
        
        linear_path = os.path.join(report_dir, linear_filename)
        soil_class_path = os.path.join(report_dir, soil_class_filename)
        
        # Create temporary directory
        temp_download_dir = tempfile.mkdtemp()
        
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(20, 'Initializing soil survey scraper...')
        else:
            tracker.update_step(step_index, 'in_progress', 20, 'Initializing soil survey scraper...')
        
        # Initialize scraper
        config = SoilScraperConfig(download_directory=temp_download_dir, wait_time=90)
        scraper = WebSoilSurveyScraper(config)
        
        try:
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(40, 'Accessing USDA soil survey website...')
            else:
                tracker.update_step(step_index, 'in_progress', 40, 'Accessing USDA soil survey website...')
            
            # Execute scraping
            success, error_msg, temp_paths = scraper.run_soil_survey(address=address)
            
            if not success:
                return {'success': False, 'message': error_msg, 'paths': []}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(80, 'Processing soil survey reports...')
            else:
                tracker.update_step(step_index, 'in_progress', 80, 'Processing soil survey reports...')
            
            # Process downloaded files
            saved_paths = []
            
            if len(temp_paths) >= 1 and os.path.exists(temp_paths[0]):
                shutil.copy2(temp_paths[0], linear_path)
                saved_paths.append(linear_path)
                
            if len(temp_paths) >= 2 and os.path.exists(temp_paths[1]):
                shutil.copy2(temp_paths[1], soil_class_path)
                saved_paths.append(soil_class_path)
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(95, f'Saved {len(saved_paths)} soil reports')
            else:
                tracker.update_step(step_index, 'in_progress', 95, f'Saved {len(saved_paths)} soil reports')
            
            return {
                'success': True,
                'message': f'Generated {len(saved_paths)} soil reports successfully',
                'paths': saved_paths
            }
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in _execute_soil_survey_with_progress: {str(e)}")
        return {'success': False, 'message': str(e), 'paths': []}
    finally:
        # Clean up temporary directory
        if temp_download_dir:
            try:
                shutil.rmtree(temp_download_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to remove temporary directory: {str(e)}")

##############################################################################

def _execute_unified_scraping_with_progress(session_id, project_data, address, asce_options):
    """
    Execute all scraping operations with real progress tracking
    """
    tracker = ProgressTracker(session_id)
    project_number = project_data['code']
    
    try:
        # Ensure project directory exists
        project_dir = _ensure_project_directory_structure(project_number)
        if not project_dir:
            tracker.set_error(f'Failed to create/access project directory for {project_number}')
            return
        
        logger.info(f"Starting unified scraping for project {project_number} (Session: {session_id})")
        
        # Step 1: ASCE Full Report PDF
        tracker.update_step(0, 'in_progress', 0, 'Starting ASCE Full Report generation...')
        result_1 = _execute_asce_full_report_with_progress(
            project_number, address, asce_options, project_dir, tracker, 0
        )
        
        if not result_1['success']:
            tracker.set_error(f"ASCE Full Report failed: {result_1['message']}")
            return
        
        tracker.update_step(0, 'completed', 100, 'ASCE Full Report completed successfully')
        
        # Step 2: USDA Soil Survey Reports
        tracker.update_step(1, 'in_progress', 0, 'Starting USDA Soil Survey generation...')
        result_2 = _execute_soil_survey_with_progress(
            project_number, address, project_dir, tracker, 1
        )
        
        if not result_2['success']:
            tracker.set_error(f"Soil Survey failed: {result_2['message']}")
            return
            
        tracker.update_step(1, 'completed', 100, 'Soil Survey reports completed successfully')
        
        # Step 3: ASCE Summary Table
        tracker.update_step(2, 'in_progress', 0, 'Starting ASCE Summary generation...')
        result_3 = _execute_asce_summary_with_progress(
            project_number, address, asce_options, tracker, 2
        )
        
        if not result_3['success']:
            tracker.set_error(f"ASCE Summary failed: {result_3['message']}")
            return
            
        tracker.update_step(2, 'completed', 100, 'ASCE Summary completed successfully')
        
        logger.info(f"Completed unified scraping for project {project_number}")
        
    except Exception as e:
        logger.error(f"Error in unified scraping sequence: {str(e)}")
        tracker.set_error(f"Unexpected error: {str(e)}")

#################################################################