"""
Copyright (c) 2008-2022 synodriver <synodriver@gmail.com>
"""
import asyncio
from aioSMART import DeviceList, Device


async def main():
    lst = await DeviceList.new()
    # print(lst)
    for hdd in lst.devices:
        # l[1].c
        await hdd.update()
        print(f"发现 {hdd.model} 硬盘 容量{hdd.capacity} 温度 {hdd.temperature}" )
        print(list(filter(lambda x: x, hdd.attributes)))


asyncio.run(main())
