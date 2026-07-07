cmake_minimum_required(VERSION 3.20 FATAL_ERROR)
find_package(cetmodules REQUIRED)
project(pdsoffset VERSION 1.00.00 LANGUAGES CXX)

include(CetCMakeEnv)
cet_cmake_env()
cet_set_compiler_flags(DIAGS CAUTIOUS WERROR EXTRA_FLAGS -pedantic)

find_package(art REQUIRED EXPORT)
find_package(art_root_io REQUIRED EXPORT)
find_package(canvas REQUIRED EXPORT)
find_package(fhiclcpp REQUIRED EXPORT)
find_package(messagefacility REQUIRED EXPORT)
find_package(ROOT REQUIRED EXPORT)
find_package(lardataobj REQUIRED EXPORT)
find_package(larcore REQUIRED EXPORT)
find_package(larcorealg REQUIRED EXPORT)
find_package(larcoreobj REQUIRED EXPORT)
find_package(dunedetdataformats REQUIRED EXPORT)

include(ArtMake)
include(BuildPlugins)

add_subdirectory(pdsoffset)

cet_cmake_config()
