cmake_minimum_required(VERSION 3.16)

set(_hlolli_wg_piano_top_level OFF)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  project(hlolli_wg_piano VERSION 0.1.0 LANGUAGES C)
  set(_hlolli_wg_piano_top_level ON)
endif()

set(HLOLLI_WG_PIANO_SOURCE
    "${CMAKE_CURRENT_LIST_DIR}/hlolli_wg_piano.c")

# A Csound source-tree build already knows its public headers, output folder,
# plugin suffix, and install folder. Use its helper when this project enters
# through add_subdirectory().
if(COMMAND make_plugin AND DEFINED libcsound_public_include_dirs)
  message(STATUS "hlolli_wg_piano: using Csound's make_plugin() helper")
  make_plugin(hlolli_wg_piano "${HLOLLI_WG_PIANO_SOURCE}")
  target_compile_features(hlolli_wg_piano PRIVATE c_std_11)
  target_compile_definitions(hlolli_wg_piano PRIVATE BUILD_PLUGINS)
  set_target_properties(hlolli_wg_piano PROPERTIES
    C_STANDARD 11
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
    C_VISIBILITY_PRESET hidden
    EXPORT_NAME wg_piano)
  if(TARGET sync_build_include_headers)
    add_dependencies(hlolli_wg_piano sync_build_include_headers)
  endif()
  add_library(hlolli::wg_piano ALIAS hlolli_wg_piano)
  return()
endif()

set(HLOLLI_CSOUND_INCLUDE_DIR "" CACHE PATH
    "Directory containing generated Csound headers such as csdl.h and version.h")

set(_hlolli_default_csound_build
    "${CMAKE_CURRENT_LIST_DIR}/../csound/build")
if(NOT EXISTS "${_hlolli_default_csound_build}/include/csdl.h")
  set(_hlolli_default_csound_build "")
endif()
set(HLOLLI_CSOUND_BUILD_DIR "${_hlolli_default_csound_build}" CACHE PATH
    "Csound build tree; its include directory must contain generated headers")

set(HLOLLI_WG_PIANO_CUSTOM_CMAKE
    "${CMAKE_CURRENT_LIST_DIR}/Custom.cmake" CACHE FILEPATH
    "Optional local CMake settings file")
if(EXISTS "${HLOLLI_WG_PIANO_CUSTOM_CMAKE}")
  message(STATUS
      "hlolli_wg_piano: including ${HLOLLI_WG_PIANO_CUSTOM_CMAKE}")
  include("${HLOLLI_WG_PIANO_CUSTOM_CMAKE}")
endif()

# Keep the older variable used by cautious-disco as a compatibility input.
if(NOT HLOLLI_CSOUND_INCLUDE_DIR AND DEFINED CSOUND_INCLUDE_DIR
    AND NOT "${CSOUND_INCLUDE_DIR}" STREQUAL "")
  set(HLOLLI_CSOUND_INCLUDE_DIR "${CSOUND_INCLUDE_DIR}")
endif()

if(NOT HLOLLI_CSOUND_INCLUDE_DIR AND HLOLLI_CSOUND_BUILD_DIR)
  find_path(_hlolli_csound_build_include
    NAMES csdl.h
    HINTS "${HLOLLI_CSOUND_BUILD_DIR}/include"
    NO_DEFAULT_PATH)
  if(_hlolli_csound_build_include)
    set(HLOLLI_CSOUND_INCLUDE_DIR "${_hlolli_csound_build_include}")
  endif()
endif()

function(_hlolli_find_csound_header_target result)
  foreach(candidate IN ITEMS
      Csound::CsoundLib64 Csound::CsoundLib Csound::Csound
      CsoundLib64 CsoundLib)
    if(TARGET "${candidate}")
      get_target_property(candidate_includes "${candidate}"
                          INTERFACE_INCLUDE_DIRECTORIES)
      if(candidate_includes
          AND NOT candidate_includes MATCHES "-NOTFOUND$")
        set("${result}" "${candidate}" PARENT_SCOPE)
        return()
      endif()
    endif()
  endforeach()
  set("${result}" "" PARENT_SCOPE)
endfunction()

set(_hlolli_csound_header_target "")
if(NOT HLOLLI_CSOUND_INCLUDE_DIR)
  _hlolli_find_csound_header_target(_hlolli_csound_header_target)
endif()

if(NOT HLOLLI_CSOUND_INCLUDE_DIR AND NOT _hlolli_csound_header_target)
  find_package(Csound 7 CONFIG QUIET)
  _hlolli_find_csound_header_target(_hlolli_csound_header_target)
endif()

if(NOT HLOLLI_CSOUND_INCLUDE_DIR AND NOT _hlolli_csound_header_target)
  find_path(HLOLLI_CSOUND_INCLUDE_DIR
    NAMES csdl.h
    HINTS
      "$ENV{CSOUND_INCLUDE_DIR}"
      "$ENV{CSOUND_HOME}/include"
      "$ENV{CSOUND_HOME}/Headers"
      "$ENV{HOME}/Library/Frameworks/CsoundLib64.framework/Headers"
      "/Library/Frameworks/CsoundLib64.framework/Headers"
      "/Applications/Csound/CsoundLib64.framework/Headers"
    PATH_SUFFIXES csound Headers)
endif()

if(HLOLLI_CSOUND_INCLUDE_DIR)
  foreach(required_header IN ITEMS csdl.h version.h float-version.h)
    if(NOT EXISTS "${HLOLLI_CSOUND_INCLUDE_DIR}/${required_header}")
      message(FATAL_ERROR
        "HLOLLI_CSOUND_INCLUDE_DIR=${HLOLLI_CSOUND_INCLUDE_DIR} lacks "
        "${required_header}. For a Csound source checkout, point to "
        "<csound-build>/include, not <csound-source>/include.")
    endif()
  endforeach()
elseif(NOT _hlolli_csound_header_target)
  message(FATAL_ERROR
    "Could not find generated Csound headers. Pass either "
    "-DHLOLLI_CSOUND_BUILD_DIR=/path/to/csound/build or "
    "-DHLOLLI_CSOUND_INCLUDE_DIR=/path/containing/csdl.h.")
endif()

if(APPLE)
  add_library(hlolli_wg_piano SHARED "${HLOLLI_WG_PIANO_SOURCE}")
else()
  add_library(hlolli_wg_piano MODULE "${HLOLLI_WG_PIANO_SOURCE}")
endif()

target_compile_features(hlolli_wg_piano PRIVATE c_std_11)
target_compile_definitions(hlolli_wg_piano PRIVATE BUILD_PLUGINS)
if(HLOLLI_CSOUND_INCLUDE_DIR)
  target_include_directories(hlolli_wg_piano PRIVATE
                             "${HLOLLI_CSOUND_INCLUDE_DIR}")
else()
  target_include_directories(hlolli_wg_piano PRIVATE
    "$<TARGET_PROPERTY:${_hlolli_csound_header_target},INTERFACE_INCLUDE_DIRECTORIES>")
endif()

if(UNIX AND NOT APPLE)
  target_link_libraries(hlolli_wg_piano PRIVATE m)
endif()

set_target_properties(hlolli_wg_piano PROPERTIES
  C_STANDARD 11
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
  C_VISIBILITY_PRESET hidden
  POSITION_INDEPENDENT_CODE YES
  EXPORT_NAME wg_piano)

if(TARGET sync_build_include_headers)
  add_dependencies(hlolli_wg_piano sync_build_include_headers)
endif()

add_library(hlolli::wg_piano ALIAS hlolli_wg_piano)

include(GNUInstallDirs)
set(_hlolli_plugin_folder "plugins64")
if(HLOLLI_CSOUND_INCLUDE_DIR
    AND EXISTS "${HLOLLI_CSOUND_INCLUDE_DIR}/version.h")
  file(STRINGS "${HLOLLI_CSOUND_INCLUDE_DIR}/version.h"
       _hlolli_csound_major_line REGEX "^#define[ \t]+CS_VERSION")
  file(STRINGS "${HLOLLI_CSOUND_INCLUDE_DIR}/version.h"
       _hlolli_csound_minor_line REGEX "^#define[ \t]+CS_SUBVER")
  string(REGEX MATCH "[0-9]+" _hlolli_csound_major
         "${_hlolli_csound_major_line}")
  string(REGEX MATCH "[0-9]+" _hlolli_csound_minor
         "${_hlolli_csound_minor_line}")
  if(NOT "${_hlolli_csound_major}" STREQUAL ""
      AND NOT "${_hlolli_csound_minor}" STREQUAL "")
    set(_hlolli_plugin_folder
        "plugins64-${_hlolli_csound_major}.${_hlolli_csound_minor}")
  endif()
endif()

if(DEFINED PLUGIN_INSTALL_DIR AND NOT "${PLUGIN_INSTALL_DIR}" STREQUAL "")
  set(_hlolli_default_install_dir "${PLUGIN_INSTALL_DIR}")
else()
  set(_hlolli_default_install_dir
      "${CMAKE_INSTALL_LIBDIR}/csound/${_hlolli_plugin_folder}")
endif()
set(HLOLLI_CSOUND_PLUGIN_DIR "${_hlolli_default_install_dir}" CACHE STRING
    "Csound runtime plugin install directory")
option(HLOLLI_WG_PIANO_INSTALL "Install the Csound runtime module"
       ${_hlolli_wg_piano_top_level})
if(HLOLLI_WG_PIANO_INSTALL)
  install(TARGETS hlolli_wg_piano
    LIBRARY DESTINATION "${HLOLLI_CSOUND_PLUGIN_DIR}"
    RUNTIME DESTINATION "${HLOLLI_CSOUND_PLUGIN_DIR}"
    COMPONENT Runtime)
endif()

option(HLOLLI_WG_PIANO_BUILD_TESTS "Add the native Csound smoke test"
       ${_hlolli_wg_piano_top_level})
if(HLOLLI_WG_PIANO_BUILD_TESTS)
  enable_testing()
  set(CSOUND_EXECUTABLE "" CACHE FILEPATH "Path to the Csound executable")
  if(NOT CSOUND_EXECUTABLE)
    find_program(CSOUND_EXECUTABLE NAMES csound csound64)
  endif()
  if(CSOUND_EXECUTABLE)
    add_test(NAME hlolli_wg_piano.smoke
      COMMAND "${CSOUND_EXECUTABLE}"
              "--opcode-lib=$<TARGET_FILE:hlolli_wg_piano>"
              -n -d -m128
              "${CMAKE_CURRENT_LIST_DIR}/tests/smoke.csd")
  else()
    message(WARNING
      "Csound was not found; the plugin will build but its smoke test is off.")
  endif()
endif()
