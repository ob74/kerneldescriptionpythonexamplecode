cmake_minimum_required(VERSION 3.10)
project(app_initializer)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Add source files
add_library(app_initializer_lib
    src/app_initializer.cpp
)

# Add include directories
target_include_directories(app_initializer_lib PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Add test executable
add_executable(test_app_initializer
    test/test_app_initializer.cpp
)

# Link test executable with the library
target_link_libraries(test_app_initializer
    app_initializer_lib
) 