
cmake_minimum_required(VERSION 2.6)

########### next target ###############

set(isprefix.driver_SRCS 
isprefix.driver.c
isprefix.c
isprefix.h
)


add_executable(isprefix.driver ${isprefix.driver_SRCS})